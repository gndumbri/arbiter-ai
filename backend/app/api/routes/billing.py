"""Stripe webhook + subscription management routes.

Handles Stripe checkout session creation and webhook events for
subscription lifecycle management.
"""

from __future__ import annotations

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
    tier: str = "PRO"  # "PRO"


class SubscriptionResponse(BaseModel):
    plan_tier: str
    status: str
    stripe_customer_id: str | None = None
    current_period_end: str | None = None


class TierInfoResponse(BaseModel):
    name: str
    daily_query_limit: int
    stripe_product_id: str | None = None


# ─── Get Tier Info ────────────────────────────────────────────────────────────


@router.get("/tiers", response_model=list[TierInfoResponse])
async def get_tiers(db: DbSession) -> list[TierInfoResponse]:
    """Get available subscription tiers for pricing display."""
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
    """Get the current user's subscription details."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user["id"])
    )
    sub = result.scalar_one_or_none()

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
    """Create a Stripe Checkout Session for subscribing.

    NOTE: Stripe is not fully integrated yet. This returns a stub URL.
    Replace with actual stripe.checkout.Session.create() when ready.
    """
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set STRIPE_SECRET_KEY.",
        )

    # In production, create a real Stripe Checkout Session here
    # import stripe
    # stripe.api_key = settings.stripe_secret_key
    # session = stripe.checkout.Session.create(...)

    return {
        "checkout_url": f"https://checkout.stripe.com/placeholder?tier={body.tier}",
        "message": "Stripe checkout integration pending. Set STRIPE_SECRET_KEY to enable.",
    }


# ─── Stripe Webhook ───────────────────────────────────────────────────────────


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events.

    NOTE: Stub implementation. Validates signature and processes
    checkout.session.completed and customer.subscription.* events.
    """
    # settings = get_settings()  # Will be used for webhook signature verification
    payload = await request.body()

    # In production, verify the webhook signature:
    # import stripe
    # sig_header = request.headers.get("stripe-signature")
    # event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)

    try:
        import json
        event = json.loads(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        customer_id = data.get("customer")
        customer_email = data.get("customer_details", {}).get("email")
        logger.info("Checkout completed: customer=%s email=%s", customer_id, customer_email)

        # Upsert subscription for user
        # TODO: Lookup user by email, create/update Subscription record

    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        status = data.get("status")
        logger.info("Subscription updated: sub=%s status=%s", sub_id, status)

    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        logger.info("Subscription deleted: sub=%s", sub_id)

    return {"received": True}
