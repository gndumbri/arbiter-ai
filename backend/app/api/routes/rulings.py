"""rulings.py — Saved Rulings CRUD with privacy controls and game-based grouping.

Allows users to save verdicts from adjudication sessions, tag them for
later retrieval, and control visibility (PRIVATE, PARTY, PUBLIC).
Rulings are linked to a game_name for easy lookup ("show me all Catan rulings").

Called by: Frontend rulings page (/dashboard/rulings), chat save button
Depends on: deps.py (CurrentUser, DbSession), tables.py (SavedRuling)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import SavedRuling

router = APIRouter(prefix="/api/v1/rulings", tags=["rulings"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class SaveRulingRequest(BaseModel):
    """Request body for saving a ruling."""

    query: str
    verdict_json: dict
    game_name: str | None = None
    session_id: str | None = None
    privacy_level: str = "PRIVATE"  # "PRIVATE" | "PARTY" | "PUBLIC"
    tags: list[str] | None = None


class SavedRulingResponse(BaseModel):
    """Response shape for a saved ruling."""

    id: str
    query: str
    verdict_json: dict
    game_name: str | None
    session_id: str | None
    privacy_level: str
    tags: list[str] | None
    created_at: str | None


class GameRulingCount(BaseModel):
    """Game name with number of saved rulings."""

    game_name: str
    count: int


class UpdateRulingRequest(BaseModel):
    """Request body for updating a ruling's metadata."""

    tags: list[str] | None = None
    game_name: str | None = None
    privacy_level: str | None = None


def _ruling_to_response(r: SavedRuling) -> SavedRulingResponse:
    """Convert a SavedRuling ORM object to a response."""
    return SavedRulingResponse(
        id=str(r.id),
        query=r.query,
        verdict_json=r.verdict_json,
        game_name=r.game_name,
        session_id=str(r.session_id) if r.session_id else None,
        privacy_level=r.privacy_level,
        tags=r.tags,
        created_at=r.created_at.isoformat() if r.created_at else None,
    )


# ─── Save a Ruling ─────────────────────────────────────────────────────────────


@router.post("", response_model=SavedRulingResponse, status_code=201)
async def save_ruling(body: SaveRulingRequest, user: CurrentUser, db: DbSession) -> SavedRulingResponse:
    """Save a verdict to the user's collection.

    Auth: JWT required.
    Rate limit: None (saving is passive, doesn't trigger LLM).
    Tier: All tiers (FREE, PRO, ADMIN).

    Args:
        body: Ruling data including query text, verdict JSON, game_name,
              session_id, privacy level, and tags.

    Returns:
        The saved ruling with generated ID and timestamp.
    """
    if body.privacy_level not in ("PRIVATE", "PARTY", "PUBLIC"):
        raise HTTPException(status_code=400, detail="Invalid privacy_level")

    ruling = SavedRuling(
        user_id=user["id"],
        query=body.query,
        verdict_json=body.verdict_json,
        game_name=body.game_name,
        session_id=uuid.UUID(body.session_id) if body.session_id else None,
        privacy_level=body.privacy_level,
        tags=body.tags,
    )
    db.add(ruling)
    await db.commit()
    await db.refresh(ruling)

    return _ruling_to_response(ruling)


# ─── List My Rulings ──────────────────────────────────────────────────────────


@router.get("", response_model=list[SavedRulingResponse])
async def list_my_rulings(
    user: CurrentUser,
    db: DbSession,
    game_name: str | None = Query(None, description="Filter by game name"),
) -> list[SavedRulingResponse]:
    """List the current user's saved rulings, optionally filtered by game.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Args:
        game_name: Optional filter — only return rulings for this game.

    Returns:
        Up to 100 most recent rulings for the authenticated user.
    """
    stmt = (
        select(SavedRuling)
        .where(SavedRuling.user_id == user["id"])
        .order_by(SavedRuling.created_at.desc())
        .limit(100)
    )

    if game_name:
        stmt = stmt.where(SavedRuling.game_name == game_name)

    result = await db.execute(stmt)
    return [_ruling_to_response(r) for r in result.scalars().all()]


# ─── List Ruling Games ────────────────────────────────────────────────────────


@router.get("/games", response_model=list[GameRulingCount])
async def list_ruling_games(user: CurrentUser, db: DbSession) -> list[GameRulingCount]:
    """List distinct game names with ruling counts for the current user.

    WHY: Powers the game filter sidebar on the rulings page.
    Shows "Catan (12)" / "Wingspan (3)" so users can click to filter.

    Auth: JWT required.
    Returns: List of game names + counts, ordered by most rulings first.
    """
    result = await db.execute(
        select(
            SavedRuling.game_name,
            func.count(SavedRuling.id).label("count"),
        )
        .where(SavedRuling.user_id == user["id"])
        .where(SavedRuling.game_name.is_not(None))
        .group_by(SavedRuling.game_name)
        .order_by(func.count(SavedRuling.id).desc())
    )
    rows = result.all()
    return [GameRulingCount(game_name=row.game_name, count=row.count) for row in rows]


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
    result = await db.execute(
        select(SavedRuling)
        .where(SavedRuling.privacy_level == "PUBLIC")
        .order_by(SavedRuling.created_at.desc())
        .limit(50)
    )
    return [_ruling_to_response(r) for r in result.scalars().all()]


# ─── Update Ruling ────────────────────────────────────────────────────────────


@router.patch("/{ruling_id}", response_model=SavedRulingResponse)
async def update_ruling(
    ruling_id: uuid.UUID,
    body: UpdateRulingRequest,
    user: CurrentUser,
    db: DbSession,
) -> SavedRulingResponse:
    """Update a ruling's metadata (tags, game_name, privacy level).

    Auth: JWT required (owner only — user_id must match).
    Rate limit: None.
    Tier: All tiers.
    """
    result = await db.execute(
        select(SavedRuling).where(
            SavedRuling.id == ruling_id,
            SavedRuling.user_id == user["id"],
        )
    )
    ruling = result.scalar_one_or_none()
    if not ruling:
        raise HTTPException(status_code=404, detail="Ruling not found")

    if body.tags is not None:
        ruling.tags = body.tags
    if body.game_name is not None:
        ruling.game_name = body.game_name
    if body.privacy_level is not None:
        if body.privacy_level not in ("PRIVATE", "PARTY", "PUBLIC"):
            raise HTTPException(status_code=400, detail="Invalid privacy_level")
        ruling.privacy_level = body.privacy_level

    await db.commit()
    await db.refresh(ruling)
    return _ruling_to_response(ruling)


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
    """
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
