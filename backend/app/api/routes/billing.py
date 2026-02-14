"""billing.py — Stripe checkout, webhook, and subscription management routes.

Handles subscription tier listing, user subscription retrieval,
Stripe checkout session creation, and webhook event processing for
subscription lifecycle management (checkout.session.completed,
customer.subscription.updated/deleted).

Called by: Frontend settings/billing page, Stripe webhook events
Depends on: deps.py (CurrentUser, DbSession), config.py (stripe_secret_key),
            tables.py (Subscription, SubscriptionTier)

NOTE: Stripe checkout and webhook endpoints are currently stubs.
Full integration requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET
environment variables to be configured.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.models.tables import Subscription, SubscriptionTier

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
logger = logging.getLogger(__name__)


# ─── Schemas ───────────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    """Request body for creating a Stripe checkout session."""

    tier: str = "PRO"


class SubscriptionResponse(BaseModel):
    """Response shape for a user's current subscription."""

    plan_tier: str
    status: str
    stripe_customer_id: str | None = None
    current_period_end: str | None = None


class TierInfoResponse(BaseModel):
    """Response shape for a subscription tier (used on pricing page)."""

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

    Args:
        body: Checkout request with target tier (e.g., 'PRO').

    Returns:
        Dict with checkout_url to redirect the user to Stripe.

    Raises:
        HTTPException: 503 if STRIPE_SECRET_KEY is not configured.

    NOTE: Currently returns a stub URL. Replace with real
    stripe.checkout.Session.create() when Stripe is fully configured.
    """
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set STRIPE_SECRET_KEY.",
        )

    # TODO(kasey, 2026-02-14): Replace with actual Stripe Checkout Session:
    # import stripe
    # stripe.api_key = settings.stripe_secret_key
    # session = stripe.checkout.Session.create(
    #     payment_method_types=["card"],
    #     line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
    #     mode="subscription",
    #     success_url=f"{settings.frontend_url}/settings?upgraded=true",
    #     cancel_url=f"{settings.frontend_url}/settings",
    #     customer_email=user["email"],
    # )
    # return {"checkout_url": session.url}

    return {
        "checkout_url": f"https://checkout.stripe.com/placeholder?tier={body.tier}",
        "message": "Stripe checkout integration pending. Set STRIPE_SECRET_KEY to enable.",
    }


# ─── Stripe Webhook ───────────────────────────────────────────────────────────


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events for subscription lifecycle.

    Auth: None (Stripe authenticates via webhook signature).
    Rate limit: None.
    Tier: N/A (system endpoint).

    Processes:
        - checkout.session.completed: Activate user's subscription.
        - customer.subscription.updated: Sync plan changes.
        - customer.subscription.deleted: Downgrade to FREE.

    Returns:
        Acknowledgment dict {"received": True}.

    NOTE: Currently a stub. In production, verify the webhook signature:
    stripe.Webhook.construct_event(payload, sig, webhook_secret)
    """
    # TODO(kasey, 2026-02-14): Uncomment and use settings for signature verification:
    # settings = get_settings()
    # sig_header = request.headers.get("stripe-signature")
    # event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    payload = await request.body()

    try:
        event = json.loads(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    # --- Handle checkout completion (new subscription) ---
    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        customer_email = data.get("customer_details", {}).get("email")
        logger.info("Checkout completed: customer=%s email=%s", customer_id, customer_email)
        # TODO(kasey, 2026-02-14): Lookup user by email, create/update Subscription record

    # --- Handle subscription plan changes ---
    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        status = data.get("status")
        logger.info("Subscription updated: sub=%s status=%s", sub_id, status)

    # --- Handle subscription cancellation ---
    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        logger.info("Subscription deleted: sub=%s", sub_id)
        # TODO(kasey, 2026-02-14): Downgrade user to FREE tier

    return {"received": True}
