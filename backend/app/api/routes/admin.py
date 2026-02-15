"""admin.py — Admin dashboard, user management, and tier configuration.

Provides admin-only endpoints for viewing system statistics, managing
user roles, publisher verification, and subscription tier limits.

Called by: Frontend admin page (/dashboard/admin)
Depends on: deps.py (CurrentUser, DbSession), tables.py (User, Publisher, etc.)
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession
from app.models.tables import (
    Publisher,
    QueryAuditLog,
    RulesetMetadata,
    Session,
    SubscriptionTier,
    User,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = structlog.get_logger()


# ── Schemas ───────────────────────────────────────────────────────────────────


class UpdateUserRoleRequest(BaseModel):
    """WHY: Pydantic model instead of raw dict prevents mass-assignment."""
    role: str = Field(..., pattern="^(USER|ADMIN)$")


class UpdatePublisherRequest(BaseModel):
    """WHY: Validates publisher fields with length/email constraints."""
    name: str | None = Field(None, min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    verified: bool | None = None


class UpdateTierRequest(BaseModel):
    """WHY: Constrains daily_query_limit to a sane range (-1 = unlimited)."""
    daily_query_limit: int = Field(..., ge=-1, le=10000)


# ─── Admin Guard ───────────────────────────────────────────────────────────────


def _require_admin(user: dict) -> None:
    """Raise 403 if user is not an admin.

    Args:
        user: The current user context dict from the auth dependency.

    Raises:
        HTTPException: 403 if user role is not ADMIN.
    """
    if user.get("role", "USER") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")


# ─── Dashboard Stats ──────────────────────────────────────────────────────────


@router.get("/stats")
async def get_admin_stats(user: CurrentUser, db: DbSession) -> dict:
    """Get system-wide statistics for the admin dashboard.

    Auth: JWT required (admin only).
    Rate limit: None (admin endpoints are not rate-limited).
    Tier: ADMIN role required.

    Returns:
        Dict with total counts for users, sessions, queries, rulesets, publishers.
    """
    _require_admin(user)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    total_sessions = (await db.execute(select(func.count(Session.id)))).scalar_one()
    total_queries = (await db.execute(select(func.count(QueryAuditLog.id)))).scalar_one()
    total_rulesets = (await db.execute(select(func.count(RulesetMetadata.id)))).scalar_one()
    total_publishers = (await db.execute(select(func.count(Publisher.id)))).scalar_one()

    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_queries": total_queries,
        "total_rulesets": total_rulesets,
        "total_publishers": total_publishers,
    }


# ─── User Management ──────────────────────────────────────────────────────────


@router.get("/users")
async def list_users(user: CurrentUser, db: DbSession) -> list[dict]:
    """List all users with role and creation info.

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Returns:
        List of user dicts (id, email, name, role, created_at). Capped at 100 most recent.
    """
    _require_admin(user)

    # Cap at 100 to prevent unbounded result sets in the admin UI
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(100)
    )
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: uuid.UUID,
    body: UpdateUserRoleRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a user's role (USER or ADMIN).

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Args:
        user_id: UUID of the user to update.
        body: UpdateUserRoleRequest with validated role.

    Returns:
        Confirmation dict with user_id and new role.

    Raises:
        HTTPException: 404 if user not found.
    """
    _require_admin(user)

    result = await db.execute(
        update(User).where(User.id == user_id).values(role=body.role)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": str(user_id), "role": body.role}


# ─── Publisher Management ──────────────────────────────────────────────────────


@router.get("/publishers")
async def list_publishers(user: CurrentUser, db: DbSession) -> list[dict]:
    """List all publishers with verification status.

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Returns:
        List of publisher dicts sorted by most recent first.
    """
    _require_admin(user)

    result = await db.execute(
        select(Publisher).order_by(Publisher.created_at.desc())
    )
    publishers = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "contact_email": p.contact_email,
            "verified": p.verified,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in publishers
    ]


@router.patch("/publishers/{publisher_id}")
async def update_publisher(
    publisher_id: uuid.UUID,
    body: UpdatePublisherRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update publisher details (name, email, verification status).

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Args:
        publisher_id: UUID of the publisher to update.
        body: UpdatePublisherRequest with optional name, email, verified fields.

    Returns:
        Confirmation dict with publisher_id and list of updated field names.

    Raises:
        HTTPException: 400 if no updatable fields provided, 404 if not found.
    """
    _require_admin(user)

    # Only include fields that were explicitly set in the request
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.execute(
        update(Publisher).where(Publisher.id == publisher_id).values(**update_data)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Publisher not found")

    return {"publisher_id": str(publisher_id), "updated": list(update_data.keys())}


# ─── Subscription Tier Management ─────────────────────────────────────────────


@router.get("/tiers")
async def list_tiers(user: CurrentUser, db: DbSession) -> list[dict]:
    """List all subscription tiers with their limits.

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Returns:
        List of tier dicts (id, name, daily_query_limit).
    """
    _require_admin(user)

    result = await db.execute(select(SubscriptionTier))
    tiers = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "daily_query_limit": t.daily_query_limit,
        }
        for t in tiers
    ]


@router.patch("/tiers/{tier_id}")
async def update_tier(
    tier_id: uuid.UUID,
    body: UpdateTierRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a subscription tier's daily query limit.

    Auth: JWT required (admin only).
    Rate limit: None.
    Tier: ADMIN role required.

    Args:
        tier_id: UUID of the tier to update.
        body: UpdateTierRequest with validated daily_query_limit.

    Returns:
        Confirmation dict with tier_id and new daily_query_limit.

    Raises:
        HTTPException: 404 if tier not found.
    """
    _require_admin(user)

    result = await db.execute(
        update(SubscriptionTier)
        .where(SubscriptionTier.id == tier_id)
        .values(daily_query_limit=body.daily_query_limit)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tier not found")

    return {"tier_id": str(tier_id), "daily_query_limit": body.daily_query_limit}
