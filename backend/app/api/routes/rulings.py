"""Saved Rulings routes — Pin/Save verdicts with privacy controls.

Allows users to save verdicts from adjudication, tag them, and control
visibility (PRIVATE, PARTY, PUBLIC).
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
    query: str
    verdict_json: dict
    privacy_level: str = "PRIVATE"  # "PRIVATE" | "PARTY" | "PUBLIC"
    tags: list[str] | None = None


class SavedRulingResponse(BaseModel):
    id: str
    query: str
    verdict_json: dict
    privacy_level: str
    tags: list[str] | None
    created_at: str | None


# ─── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=SavedRulingResponse, status_code=201)
async def save_ruling(body: SaveRulingRequest, user: CurrentUser, db: DbSession) -> SavedRulingResponse:
    """Save a verdict to the user's collection."""
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


@router.get("", response_model=list[SavedRulingResponse])
async def list_my_rulings(user: CurrentUser, db: DbSession) -> list[SavedRulingResponse]:
    """List the current user's saved rulings."""
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


@router.get("/public", response_model=list[SavedRulingResponse])
async def list_public_rulings(db: DbSession) -> list[SavedRulingResponse]:
    """List public rulings from all users."""
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


@router.patch("/{ruling_id}/privacy")
async def update_ruling_privacy(
    ruling_id: uuid.UUID,
    body: dict,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update the privacy level of a saved ruling."""
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


@router.delete("/{ruling_id}", status_code=204)
async def delete_ruling(
    ruling_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a saved ruling."""
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
