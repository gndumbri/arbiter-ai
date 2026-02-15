"""rulings.py — Saved Rulings CRUD with privacy controls.

Allows users to save verdicts from adjudication sessions, tag them for
later retrieval, and control visibility (PRIVATE, PARTY, PUBLIC).
Public rulings feed into the community discovery page.

Called by: Frontend rulings page (/dashboard/rulings), chat save button
Depends on: deps.py (CurrentUser, DbSession), tables.py (SavedRuling)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import SavedRuling

router = APIRouter(prefix="/api/v1/rulings", tags=["rulings"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class SaveRulingRequest(BaseModel):
    """Request body for saving a ruling."""

    query: str
    verdict_json: dict
    privacy_level: str = "PRIVATE"  # "PRIVATE" | "PARTY" | "PUBLIC"
    tags: list[str] | None = None


class SavedRulingResponse(BaseModel):
    """Response shape for a saved ruling."""

    id: str
    query: str
    verdict_json: dict
    privacy_level: str
    tags: list[str] | None
    created_at: str | None


# ─── Save a Ruling ─────────────────────────────────────────────────────────────


@router.post("", response_model=SavedRulingResponse, status_code=201)
async def save_ruling(body: SaveRulingRequest, user: CurrentUser, db: DbSession) -> SavedRulingResponse:
    """Save a verdict to the user's collection.

    Auth: JWT required.
    Rate limit: None (saving is passive, doesn't trigger LLM).
    Tier: All tiers (FREE, PRO, ADMIN).

    Args:
        body: Ruling data including query text, verdict JSON, privacy level, and tags.

    Returns:
        The saved ruling with generated ID and timestamp.

    Raises:
        HTTPException: 400 if privacy_level is not one of PRIVATE/PARTY/PUBLIC.
    """
    if body.privacy_level not in ("PRIVATE", "PARTY", "PUBLIC"):
        raise HTTPException(status_code=400, detail="Invalid privacy_level")

    ruling = SavedRuling(
        user_id=user["id"],
        query=body.query,
        verdict_json=body.verdict_json,
        privacy_level=body.privacy_level,
        tags=body.tags,
    )
    db.add(ruling)
    await db.commit()
    await db.refresh(ruling)

    return SavedRulingResponse(
        id=str(ruling.id),
        query=ruling.query,
        verdict_json=ruling.verdict_json,
        privacy_level=ruling.privacy_level,
        tags=ruling.tags,
        created_at=ruling.created_at.isoformat() if ruling.created_at else None,
    )


# ─── List My Rulings ──────────────────────────────────────────────────────────


@router.get("", response_model=list[SavedRulingResponse])
async def list_my_rulings(user: CurrentUser, db: DbSession) -> list[SavedRulingResponse]:
    """List the current user's saved rulings.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Returns:
        Up to 100 most recent rulings for the authenticated user.
    """
    # Cap at 100 to avoid unbounded queries in paginated UI
    result = await db.execute(
        select(SavedRuling)
        .where(SavedRuling.user_id == user["id"])
        .order_by(SavedRuling.created_at.desc())
        .limit(100)
    )
    rulings = result.scalars().all()

    return [
        SavedRulingResponse(
            id=str(r.id),
            query=r.query,
            verdict_json=r.verdict_json,
            privacy_level=r.privacy_level,
            tags=r.tags,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rulings
    ]


# ─── Public Community Feed ────────────────────────────────────────────────────


@router.get("/public", response_model=list[SavedRulingResponse])
async def list_public_rulings(db: DbSession) -> list[SavedRulingResponse]:
    """List public rulings from all users for the community feed.

    Auth: None (public endpoint).
    Rate limit: None.
    Tier: Open to all.

    Returns:
        Up to 50 most recent PUBLIC rulings across all users.
    """
    # Limit to 50 for the community feed — pagination can be added later
    result = await db.execute(
        select(SavedRuling)
        .where(SavedRuling.privacy_level == "PUBLIC")
        .order_by(SavedRuling.created_at.desc())
        .limit(50)
    )
    rulings = result.scalars().all()

    return [
        SavedRulingResponse(
            id=str(r.id),
            query=r.query,
            verdict_json=r.verdict_json,
            privacy_level=r.privacy_level,
            tags=r.tags,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rulings
    ]


# ─── Update Privacy Level ─────────────────────────────────────────────────────


@router.patch("/{ruling_id}/privacy")
async def update_ruling_privacy(
    ruling_id: uuid.UUID,
    body: dict,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update the privacy level of a saved ruling.

    Auth: JWT required (owner only — user_id must match).
    Rate limit: None.
    Tier: All tiers.

    Args:
        ruling_id: UUID of the ruling to update.
        body: Dict with 'privacy_level' set to PRIVATE, PARTY, or PUBLIC.

    Returns:
        Confirmation dict with ruling ID and new privacy level.

    Raises:
        HTTPException: 404 if ruling not found or not owned by user.
    """
    # Ownership check: only the creator can change privacy
    result = await db.execute(
        select(SavedRuling).where(
            SavedRuling.id == ruling_id,
            SavedRuling.user_id == user["id"],
        )
    )
    ruling = result.scalar_one_or_none()
    if not ruling:
        raise HTTPException(status_code=404, detail="Ruling not found")

    new_privacy = body.get("privacy_level", ruling.privacy_level)
    if new_privacy not in ("PRIVATE", "PARTY", "PUBLIC"):
        raise HTTPException(status_code=400, detail="Invalid privacy_level")

    ruling.privacy_level = new_privacy
    await db.commit()

    return {"id": str(ruling.id), "privacy_level": ruling.privacy_level}


# ─── Delete Ruling ─────────────────────────────────────────────────────────────


@router.delete("/{ruling_id}", status_code=204)
async def delete_ruling(
    ruling_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a saved ruling.

    Auth: JWT required (owner only).
    Rate limit: None.
    Tier: All tiers.

    Args:
        ruling_id: UUID of the ruling to delete.

    Raises:
        HTTPException: 404 if ruling not found or not owned by user.
    """
    # Ownership check: only the creator can delete
    result = await db.execute(
        select(SavedRuling).where(
            SavedRuling.id == ruling_id,
            SavedRuling.user_id == user["id"],
        )
    )
    ruling = result.scalar_one_or_none()
    if not ruling:
        raise HTTPException(status_code=404, detail="Ruling not found")

    await db.delete(ruling)
    await db.commit()
