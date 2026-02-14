"""library.py — User Game Library CRUD routes.

Manages the user's personal game library — games they've added from
the catalog or manually, with notes, favorites, and last-played tracking.

Endpoints:
    GET    /api/v1/library           → List user's library entries
    POST   /api/v1/library           → Add a game to the library
    PATCH  /api/v1/library/{id}      → Update notes/favorite/last_played
    DELETE /api/v1/library/{id}      → Remove a game from the library
    PATCH  /api/v1/library/{id}/favorite → Toggle favorite status

Called by: Frontend catalog page ("Add to Library" button),
           future library dashboard page.
Depends on: deps.py (CurrentUser, DbSession),
            tables.py (UserGameLibrary)

Architecture note for AI agents:
    The UserGameLibrary model was defined in tables.py but had zero API
    routes prior to this file. The frontend catalog page has an
    "Add to Library" button that now calls POST /library via api.ts.
    Each library entry links a user to a game_slug (unique per user).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import UserGameLibrary

router = APIRouter(prefix="/api/v1/library", tags=["library"])
logger = logging.getLogger(__name__)


# ─── Schemas ───────────────────────────────────────────────────────────────────


class AddToLibraryRequest(BaseModel):
    """Request body for adding a game to the user's library.

    Fields:
        game_slug: URL-safe identifier for the game (e.g. 'dnd-5e').
        game_name: Human-readable display name (e.g. 'Dungeons & Dragons 5E').
        official_ruleset_id: Optional UUID of the official catalog ruleset.
        notes: Optional user notes about the game.
    """

    game_slug: str
    game_name: str
    official_ruleset_id: str | None = None
    notes: str | None = None


class UpdateLibraryRequest(BaseModel):
    """Request body for updating a library entry.

    All fields are optional — only provided fields are updated.

    Fields:
        notes: User's notes about the game.
        favorite: Whether this game is a favorite.
        last_played_at: ISO timestamp of when the game was last played.
    """

    notes: str | None = None
    favorite: bool | None = None
    last_played_at: str | None = None


class LibraryEntryResponse(BaseModel):
    """Response shape for a single library entry.

    Used by GET /library (as a list) and POST /library (single item).
    """

    id: str
    game_slug: str
    game_name: str
    added_from_catalog: bool
    official_ruleset_id: str | None
    notes: str | None
    favorite: bool
    last_played_at: str | None
    created_at: str


def _serialize_entry(entry: UserGameLibrary) -> LibraryEntryResponse:
    """Convert a UserGameLibrary ORM object to a response model.

    Centralizes serialization to avoid repeating .isoformat() logic.

    Args:
        entry: SQLAlchemy UserGameLibrary instance.

    Returns:
        LibraryEntryResponse with all fields serialized.
    """
    return LibraryEntryResponse(
        id=str(entry.id),
        game_slug=entry.game_slug,
        game_name=entry.game_name,
        added_from_catalog=entry.added_from_catalog or False,
        official_ruleset_id=str(entry.official_ruleset_id) if entry.official_ruleset_id else None,
        notes=entry.notes,
        favorite=entry.favorite or False,
        last_played_at=entry.last_played_at.isoformat() if entry.last_played_at else None,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


# ─── List Library ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[LibraryEntryResponse])
async def list_library(user: CurrentUser, db: DbSession) -> list[LibraryEntryResponse]:
    """List all games in the current user's library.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Returns:
        List of library entries, favorites first, then by created_at descending.
    """
    result = await db.execute(
        select(UserGameLibrary)
        .where(UserGameLibrary.user_id == user["id"])
        .order_by(UserGameLibrary.favorite.desc(), UserGameLibrary.created_at.desc())
    )
    entries = result.scalars().all()
    return [_serialize_entry(e) for e in entries]


# ─── Add to Library ──────────────────────────────────────────────────────────


@router.post("", response_model=LibraryEntryResponse, status_code=201)
async def add_to_library(
    body: AddToLibraryRequest, user: CurrentUser, db: DbSession
) -> LibraryEntryResponse:
    """Add a game to the user's library.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Args:
        body: Game details to add (game_slug, game_name, etc.).

    Returns:
        The newly created library entry.

    Raises:
        HTTPException: 409 if the game is already in the user's library.
    """
    # Check for duplicate — each user can only have one entry per game_slug
    result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.user_id == user["id"],
            UserGameLibrary.game_slug == body.game_slug,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Game '{body.game_slug}' is already in your library.",
        )

    entry = UserGameLibrary(
        id=uuid.uuid4(),
        user_id=user["id"],
        game_slug=body.game_slug,
        game_name=body.game_name,
        added_from_catalog=body.official_ruleset_id is not None,
        official_ruleset_id=uuid.UUID(body.official_ruleset_id) if body.official_ruleset_id else None,
        notes=body.notes,
        favorite=False,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    logger.info("Library entry created: user=%s game=%s", user["id"], body.game_slug)
    return _serialize_entry(entry)


# ─── Update Library Entry ────────────────────────────────────────────────────


@router.patch("/{entry_id}", response_model=LibraryEntryResponse)
async def update_library_entry(
    entry_id: str, body: UpdateLibraryRequest, user: CurrentUser, db: DbSession
) -> LibraryEntryResponse:
    """Update a library entry's notes, favorite status, or last-played date.

    Auth: JWT required (must own the entry).
    Rate limit: None.
    Tier: All tiers.

    Args:
        entry_id: UUID of the library entry to update.
        body: Fields to update (notes, favorite, last_played_at).

    Returns:
        The updated library entry.

    Raises:
        HTTPException: 404 if entry not found or doesn't belong to user.
    """
    result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.id == uuid.UUID(entry_id),
            UserGameLibrary.user_id == user["id"],
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found.")

    if body.notes is not None:
        entry.notes = body.notes
    if body.favorite is not None:
        entry.favorite = body.favorite
    if body.last_played_at is not None:
        entry.last_played_at = datetime.fromisoformat(body.last_played_at)

    await db.commit()
    await db.refresh(entry)
    return _serialize_entry(entry)


# ─── Toggle Favorite ──────────────────────────────────────────────────────────


@router.patch("/{entry_id}/favorite")
async def toggle_favorite(entry_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Toggle the favorite status of a library entry.

    Auth: JWT required (must own the entry).
    Rate limit: None.
    Tier: All tiers.

    WHY a separate endpoint: The frontend catalog/library page has a
    star/heart button that toggles with a single click. A dedicated
    endpoint avoids requiring the full UpdateLibraryRequest payload.

    Args:
        entry_id: UUID of the library entry.

    Returns:
        Dict with {id, favorite} reflecting the new state.

    Raises:
        HTTPException: 404 if entry not found or doesn't belong to user.
    """
    result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.id == uuid.UUID(entry_id),
            UserGameLibrary.user_id == user["id"],
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found.")

    # WHY: Simple toggle — no request body needed for a favorite button click
    entry.favorite = not entry.favorite
    await db.commit()

    return {"id": str(entry.id), "favorite": entry.favorite}


# ─── Delete Library Entry ─────────────────────────────────────────────────────


@router.delete("/{entry_id}", status_code=204)
async def remove_from_library(entry_id: str, user: CurrentUser, db: DbSession) -> None:
    """Remove a game from the user's library.

    Auth: JWT required (must own the entry).
    Rate limit: None.
    Tier: All tiers.

    Args:
        entry_id: UUID of the library entry to delete.

    Raises:
        HTTPException: 404 if entry not found or doesn't belong to user.
    """
    result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.id == uuid.UUID(entry_id),
            UserGameLibrary.user_id == user["id"],
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found.")

    await db.delete(entry)
    await db.commit()
    logger.info("Library entry deleted: user=%s entry=%s", user["id"], entry_id)
