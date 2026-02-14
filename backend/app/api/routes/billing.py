"""billing.py — Stripe checkout, webhook, and subscription management routes.

Handles subscription tier listing, user subscription retrieval,
Stripe Checkout Session creation, and webhook event processing for
the full subscription lifecycle:
  - checkout.session.completed → activate PRO subscription
  - customer.subscription.updated → sync plan/status changes
  - customer.subscription.deleted → downgrade to FREE

Called by: Frontend settings/billing page, Stripe webhook events
Depends on: deps.py (CurrentUser, DbSession), config.py (stripe keys),
            tables.py (Subscription, SubscriptionTier, User)

Architecture note for AI agents:
  The checkout flow works as follows:
  1. Frontend calls POST /billing/checkout → gets a Stripe Checkout URL
  2. User completes payment on Stripe's hosted page
  3. Stripe fires a webhook to POST /billing/webhooks/stripe
  4. Webhook handler creates/updates the Subscription row in Postgres
  5. The deps.py auth dependency reads the Subscription table on every
     request to resolve the user's tier (FREE or PRO).
"""

from __future__ import annotations

import json
import logging
import uuid

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models.tables import Subscription, SubscriptionTier, User

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
logger = logging.getLogger(__name__)


# ─── Schemas ───────────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    """Request body for creating a Stripe checkout session.

    Fields:
        tier: Target subscription tier (default 'PRO'). Must match a
              SubscriptionTier.name in the database.
    """

    tier: str = "PRO"


class SubscriptionResponse(BaseModel):
    """Response shape for a user's current subscription.

    Returned by GET /billing/subscription. Users without a Subscription
    row default to FREE tier with status='active'.
    """

    plan_tier: str
    status: str
    stripe_customer_id: str | None = None
    current_period_end: str | None = None


class TierInfoResponse(BaseModel):
    """Response shape for a subscription tier (used on pricing page).

    Returned by GET /billing/tiers. Public endpoint — no auth required.
    """

    name: str
    daily_query_limit: int
    stripe_product_id: str | None = None


# ─── Get Tier Info ────────────────────────────────────────────────────────────


@router.get("/tiers", response_model=list[TierInfoResponse])
async def get_tiers(db: DbSession) -> list[TierInfoResponse]:
    """Get available subscription tiers for the pricing page.

    Auth: None (public endpoint — pricing is visible to all).
    Rate limit: None.
    Tier: Open to all.

    Returns:
        List of tiers with names, daily limits, and Stripe product IDs.
    """
    result = await db.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    return [
        TierInfoResponse(
            name=t.name,
            daily_query_limit=t.daily_query_limit,
            stripe_product_id=t.stripe_product_id,
        )
        for t in tiers
    ]


# ─── Get My Subscription ──────────────────────────────────────────────────────


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_my_subscription(user: CurrentUser, db: DbSession) -> SubscriptionResponse:
    """Get the current user's subscription details.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Returns:
        Subscription info. Defaults to FREE tier if no subscription exists.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user["id"])
    )
    sub = result.scalar_one_or_none()

    # Users without a Subscription row default to the FREE tier
    if not sub:
        return SubscriptionResponse(
            plan_tier="FREE",
            status="active",
        )

    return SubscriptionResponse(
        plan_tier=sub.plan_tier,
        status=sub.status,
        stripe_customer_id=sub.stripe_customer_id,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
    )


# ─── Create Checkout Session ──────────────────────────────────────────────────


@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, user: CurrentUser, db: DbSession) -> dict:
    """Create a Stripe Checkout Session for subscribing to a paid tier.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers (typically called by FREE users upgrading).

    Flow:
        1. Validates Stripe is configured (STRIPE_SECRET_KEY env var).
        2. Creates a Stripe Checkout Session with the configured price.
        3. Returns the checkout_url for frontend redirect.
        4. After payment, Stripe fires webhooks handled by stripe_webhook().

    Args:
        body: Checkout request with target tier (e.g., 'PRO').

    Returns:
        Dict with checkout_url to redirect the user to Stripe.

    Raises:
        HTTPException: 503 if STRIPE_SECRET_KEY is not configured.
    """
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set STRIPE_SECRET_KEY.",
        )

    # Configure stripe with the secret key for this request
    stripe.api_key = settings.stripe_secret_key

    try:
        # Create a Stripe Checkout Session for the subscription
        # WHY: We use 'subscription' mode so Stripe handles recurring billing.
        # The customer_email pre-fills the email field on the checkout page.
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.allowed_origins}/settings?upgraded=true",
            cancel_url=f"{settings.allowed_origins}/settings",
            customer_email=user["email"],
            # WHY: client_reference_id lets us link the Stripe checkout back to
            # our internal user ID in the webhook handler.
            client_reference_id=str(user["id"]),
            metadata={
                "arbiter_user_id": str(user["id"]),
                "target_tier": body.tier,
            },
        )

        logger.info(
            "Stripe checkout session created: session_id=%s user=%s tier=%s",
            checkout_session.id,
            user["id"],
            body.tier,
        )

        return {"checkout_url": checkout_session.url}

    except stripe.StripeError as exc:
        logger.exception("Stripe checkout creation failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Stripe error: {exc.user_message or str(exc)}",
        ) from exc


# ─── Stripe Webhook ───────────────────────────────────────────────────────────


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events for subscription lifecycle.

    Auth: Stripe webhook signature (not JWT — this is a server-to-server call).
    Rate limit: None.
    Tier: N/A (system endpoint).

    Processes:
        - checkout.session.completed: Create Subscription row → activates PRO.
        - customer.subscription.updated: Sync plan/status changes.
        - customer.subscription.deleted: Set subscription status to 'canceled'.

    Security: When STRIPE_WEBHOOK_SECRET is configured, the payload signature
    is verified to prevent spoofed webhook calls.

    Returns:
        Acknowledgment dict {"received": True}.
    """
    settings = get_settings()
    payload = await request.body()

    # Verify webhook signature when secret is configured
    # WHY: Without signature verification, anyone could spoof webhook events
    # and grant themselves PRO subscriptions for free.
    if settings.stripe_webhook_secret:
        sig_header = request.headers.get("stripe-signature")
        try:
            stripe.api_key = settings.stripe_secret_key
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except stripe.SignatureVerificationError as sig_exc:
            logger.warning("Stripe webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature") from sig_exc
        except Exception as exc:
            logger.warning("Stripe webhook parse error: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid payload") from exc
    else:
        # Development fallback: parse without verification
        logger.warning("STRIPE_WEBHOOK_SECRET not set — webhook signature verification disabled")
        try:
            event = json.loads(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid payload") from exc

    event_type = event.get("type", "") if isinstance(event, dict) else event.type
    data = (
        event.get("data", {}).get("object", {})
        if isinstance(event, dict)
        else event.data.object
    )

    # --- Handle checkout completion (new subscription) ---
    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)

    # --- Handle subscription plan changes ---
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)

    # --- Handle subscription cancellation ---
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)

    else:
        logger.info("Unhandled Stripe event type: %s", event_type)

    return {"received": True}


# ─── Webhook Helpers ──────────────────────────────────────────────────────────


async def _handle_checkout_completed(data: dict, db: DbSession) -> None:
    """Process a completed Stripe checkout — create/update the Subscription row.

    Uses the client_reference_id (our user UUID) set during checkout creation
    to link the Stripe customer to the correct Arbiter user.

    Args:
        data: The Stripe checkout.session.completed event data object.
        db: Async database session.
    """
    customer_id = (
        data.get("customer") if isinstance(data, dict)
        else getattr(data, "customer", None)
    )
    user_id_str = (
        data.get("client_reference_id") if isinstance(data, dict)
        else getattr(data, "client_reference_id", None)
    )
    customer_email = (
        data.get("customer_details", {}).get("email")
        if isinstance(data, dict)
        else getattr(getattr(data, "customer_details", None), "email", None)
    )
    metadata = (
        data.get("metadata", {}) if isinstance(data, dict)
        else getattr(data, "metadata", {})
    )
    target_tier = (
        metadata.get("target_tier", "PRO") if isinstance(metadata, dict)
        else getattr(metadata, "target_tier", "PRO")
    )

    logger.info(
        "Checkout completed: customer=%s email=%s user_id=%s tier=%s",
        customer_id, customer_email, user_id_str, target_tier,
    )

    # Resolve the user — first by client_reference_id, then by email
    user = None
    if user_id_str:
        try:
            user_uuid = uuid.UUID(user_id_str)
            result = await db.execute(select(User).where(User.id == user_uuid))
            user = result.scalar_one_or_none()
        except ValueError:
            pass

    if user is None and customer_email:
        result = await db.execute(select(User).where(User.email == customer_email))
        user = result.scalar_one_or_none()

    if user is None:
        logger.error("Checkout completed but user not found: ref=%s email=%s", user_id_str, customer_email)
        return

    # Create or update the Subscription record
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    existing_sub = result.scalar_one_or_none()

    if existing_sub:
        existing_sub.plan_tier = target_tier
        existing_sub.status = "ACTIVE"
        existing_sub.stripe_customer_id = customer_id
    else:
        new_sub = Subscription(
            id=uuid.uuid4(),
            user_id=user.id,
            plan_tier=target_tier,
            status="ACTIVE",
            stripe_customer_id=customer_id,
        )
        db.add(new_sub)

    await db.commit()
    logger.info("Subscription activated: user=%s tier=%s", user.id, target_tier)


async def _handle_subscription_updated(data: dict, db: DbSession) -> None:
    """Sync a subscription update from Stripe (plan changes, renewals).

    Args:
        data: The Stripe customer.subscription.updated event data object.
        db: Async database session.
    """
    customer_id = data.get("customer") if isinstance(data, dict) else getattr(data, "customer", None)
    sub_status = data.get("status") if isinstance(data, dict) else getattr(data, "status", None)

    if not customer_id:
        logger.warning("Subscription updated event missing customer ID")
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        # Map Stripe status to our internal status
        # WHY: Stripe uses 'active', 'past_due', 'canceled', etc.
        # We normalize to ACTIVE/PAST_DUE/CANCELED for simpler tier resolution.
        status_map = {
            "active": "ACTIVE",
            "past_due": "PAST_DUE",
            "canceled": "CANCELED",
            "unpaid": "PAST_DUE",
            "trialing": "ACTIVE",
        }
        sub.status = status_map.get(sub_status, sub_status.upper() if sub_status else "ACTIVE")
        await db.commit()
        logger.info("Subscription synced: customer=%s status=%s", customer_id, sub.status)
    else:
        logger.warning("Subscription updated but no record found: customer=%s", customer_id)


async def _handle_subscription_deleted(data: dict, db: DbSession) -> None:
    """Handle a subscription cancellation — downgrade user to FREE.

    Args:
        data: The Stripe customer.subscription.deleted event data object.
        db: Async database session.
    """
    customer_id = data.get("customer") if isinstance(data, dict) else getattr(data, "customer", None)

    if not customer_id:
        logger.warning("Subscription deleted event missing customer ID")
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()

    if sub:
        # WHY: We keep the Subscription row but mark it canceled so we
        # have an audit trail. The deps.py auth only grants PRO for
        # status == 'ACTIVE', so this effectively downgrades the user.
        sub.status = "CANCELED"
        sub.plan_tier = "FREE"
        await db.commit()
        logger.info("Subscription canceled: customer=%s downgraded to FREE", customer_id)
    else:
        logger.warning("Subscription deleted but no record found: customer=%s", customer_id)
