"""Admin routes — dashboard stats, publisher management, tier configuration.

Protected by AdminUser dependency (requires role='ADMIN').
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
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


# ─── Admin Guard ───────────────────────────────────────────────────────────────


def _require_admin(user: dict) -> None:
    """Raise 403 if user is not an admin."""
    if user.get("role", "USER") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")


# ─── Dashboard Stats ──────────────────────────────────────────────────────────


@router.get("/stats")
async def get_admin_stats(user: CurrentUser, db: DbSession) -> dict:
    """Get system-wide statistics for the admin dashboard."""
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
    """List all users with subscription info."""
    _require_admin(user)

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
    body: dict,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a user's role (USER/ADMIN)."""
    _require_admin(user)

    new_role = body.get("role", "USER")
    if new_role not in ("USER", "ADMIN"):
        raise HTTPException(status_code=400, detail="Role must be USER or ADMIN")

    result = await db.execute(
        update(User).where(User.id == user_id).values(role=new_role)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": str(user_id), "role": new_role}


# ─── Publisher Management ──────────────────────────────────────────────────────


@router.get("/publishers")
async def list_publishers(user: CurrentUser, db: DbSession) -> list[dict]:
    """List all publishers."""
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
    body: dict,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update publisher details."""
    _require_admin(user)

    update_data = {}
    if "name" in body:
        update_data["name"] = body["name"]
    if "contact_email" in body:
        update_data["contact_email"] = body["contact_email"]
    if "verified" in body:
        update_data["verified"] = body["verified"]

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
    """List all subscription tiers."""
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
    body: dict,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a subscription tier's limits."""
    _require_admin(user)

    if "daily_query_limit" not in body:
        raise HTTPException(status_code=400, detail="daily_query_limit required")

    result = await db.execute(
        update(SubscriptionTier)
        .where(SubscriptionTier.id == tier_id)
        .values(daily_query_limit=body["daily_query_limit"])
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tier not found")

    return {"tier_id": str(tier_id), "daily_query_limit": body["daily_query_limit"]}
