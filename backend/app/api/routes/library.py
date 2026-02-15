"""library.py — User Game Library CRUD routes.

Manages the user's personal game library — games they've added from
the catalog or manually, with favorites and last-queried tracking.

Endpoints:
    GET    /api/v1/library           → List user's library entries
    POST   /api/v1/library           → Add a game to the library
    PATCH  /api/v1/library/{id}      → Update favorite/last_queried
    DELETE /api/v1/library/{id}      → Remove a game from the library
    PATCH  /api/v1/library/{id}/favorite → Toggle favorite status

Called by: Frontend catalog page ("Add to Library" button),
           future library dashboard page.
Depends on: deps.py (CurrentUser, DbSession),
            tables.py (UserGameLibrary)

Architecture note for AI agents:
    The DB schema for user_game_library has columns:
    id, user_id, game_name, official_ruleset_ids (UUID[]),
    personal_ruleset_ids (UUID[]), is_favorite, last_queried, created_at.
    This route must match those columns exactly.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limit import RateLimitDep
from app.models.schemas import SessionRead
from app.models.tables import (
    OfficialRuleset,
    Publisher,
    RulesetMetadata,
    Session,
    UserGameLibrary,
)

router = APIRouter(prefix="/api/v1/library", tags=["library"])
logger = logging.getLogger(__name__)
READY_CATALOG_STATUSES = ("READY", "INDEXED", "COMPLETE", "PUBLISHED")


# ─── Schemas ───────────────────────────────────────────────────────────────────


class AddToLibraryRequest(BaseModel):
    """Request body for adding a game to the user's library.

    Fields:
        game_name: Human-readable display name (e.g. 'Dungeons & Dragons 5E').
        game_slug: URL-safe alias (frontend convenience — stored as game_name).
        official_ruleset_id: Optional single UUID — appended to official_ruleset_ids array.
    """

    game_name: str
    game_slug: str | None = None  # Accepted but mapped to game_name for compat
    official_ruleset_id: str | None = None


class UpdateLibraryRequest(BaseModel):
    """Request body for updating a library entry.

    All fields are optional — only provided fields are updated.
    """

    is_favorite: bool | None = None
    last_queried: str | None = None


class LibraryEntryResponse(BaseModel):
    """Response shape for a single library entry.

    Used by GET /library (as a list) and POST /library (single item).
    """

    id: str
    game_name: str
    game_slug: str  # Derived from game_name for frontend compat
    added_from_catalog: bool
    official_ruleset_id: str | None  # First from the array, for compat
    official_ruleset_ids: list[str] | None = None
    personal_ruleset_ids: list[str] | None = None
    is_favorite: bool
    favorite: bool  # Alias for frontend compat
    last_queried: str | None
    created_at: str


def _to_slug(name: str) -> str:
    """Convert a game name to a slug for frontend compatibility."""
    return name.lower().replace(" ", "-").replace("'", "").replace(",", "")


def _serialize_entry(entry: UserGameLibrary) -> LibraryEntryResponse:
    """Convert a UserGameLibrary ORM object to a response model."""
    first_ruleset = None
    if entry.official_ruleset_ids and len(entry.official_ruleset_ids) > 0:
        first_ruleset = str(entry.official_ruleset_ids[0])

    return LibraryEntryResponse(
        id=str(entry.id),
        game_name=entry.game_name,
        game_slug=_to_slug(entry.game_name),
        added_from_catalog=first_ruleset is not None,
        official_ruleset_id=first_ruleset,
        official_ruleset_ids=[str(rid) for rid in (entry.official_ruleset_ids or [])] or None,
        personal_ruleset_ids=[str(rid) for rid in (entry.personal_ruleset_ids or [])] or None,
        is_favorite=entry.is_favorite or False,
        favorite=entry.is_favorite or False,
        last_queried=entry.last_queried.isoformat() if entry.last_queried else None,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


# ─── List Library ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[LibraryEntryResponse])
async def list_library(user: CurrentUser, db: DbSession) -> list[LibraryEntryResponse]:
    """List all games in the current user's library.

    Auth: JWT required.
    Returns: List of library entries, favorites first, then by created_at descending.
    """
    result = await db.execute(
        select(UserGameLibrary)
        .where(UserGameLibrary.user_id == user["id"])
        .order_by(UserGameLibrary.is_favorite.desc(), UserGameLibrary.created_at.desc())
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

    Returns:
        The newly created library entry.

    Raises:
        HTTPException: 409 if the game is already in the user's library.
    """
    # Check for duplicate — each user can only have one entry per game_name
    result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.user_id == user["id"],
            UserGameLibrary.game_name == body.game_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This game is already in your library.",
        )

    # Build official_ruleset_ids array from the single ID if provided
    ruleset_ids = None
    if body.official_ruleset_id:
        with contextlib.suppress(ValueError):
            ruleset_ids = [uuid.UUID(body.official_ruleset_id)]

    entry = UserGameLibrary(
        id=uuid.uuid4(),
        user_id=user["id"],
        game_name=body.game_name,
        official_ruleset_ids=ruleset_ids,
        is_favorite=False,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    logger.info("Library entry created: user=%s game=%s", user["id"], body.game_name)
    return _serialize_entry(entry)


# ─── Update Library Entry ────────────────────────────────────────────────────


@router.patch("/{entry_id}", response_model=LibraryEntryResponse)
async def update_library_entry(
    entry_id: str, body: UpdateLibraryRequest, user: CurrentUser, db: DbSession
) -> LibraryEntryResponse:
    """Update a library entry's favorite status or last-queried date.

    Auth: JWT required (must own the entry).
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

    if body.is_favorite is not None:
        entry.is_favorite = body.is_favorite
    if body.last_queried is not None:
        entry.last_queried = datetime.fromisoformat(body.last_queried)

    await db.commit()
    await db.refresh(entry)
    return _serialize_entry(entry)


# ─── Toggle Favorite ──────────────────────────────────────────────────────────


@router.patch("/{entry_id}/favorite")
async def toggle_favorite(entry_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Toggle the favorite status of a library entry.

    Auth: JWT required (must own the entry).

    WHY a separate endpoint: The frontend has a star/heart button that
    toggles with a single click; a dedicated endpoint avoids requiring
    the full UpdateLibraryRequest payload.
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

    entry.is_favorite = not entry.is_favorite
    await db.commit()

    return {"id": str(entry.id), "favorite": entry.is_favorite}


# ─── Delete Library Entry ─────────────────────────────────────────────────────


@router.delete("/{entry_id}", status_code=204)
async def remove_from_library(entry_id: str, user: CurrentUser, db: DbSession) -> None:
    """Remove a game from the user's library.

    Auth: JWT required (must own the entry).
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


@router.post("/{entry_id}/sessions", response_model=SessionRead)
async def start_session_from_library(
    entry_id: str,
    user: CurrentUser,
    db: DbSession,
    limiter: RateLimitDep,
) -> SessionRead:
    """Start Ask flow from a shelf entry, always binding to game rules when possible.

    Behavior:
        1) Reuse the latest non-expired session for this game that already has indexed uploads.
        2) Reuse an existing non-expired session with matching official active_ruleset_ids.
        3) Otherwise create a fresh session linked to valid READY official rulesets.
        4) If no valid rules are linked at all, return 409 with an actionable message.
    """
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid library entry id.") from exc

    entry_result = await db.execute(
        select(UserGameLibrary).where(
            UserGameLibrary.id == entry_uuid,
            UserGameLibrary.user_id == user["id"],
        )
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Library entry not found.")

    now = datetime.now(UTC)

    # Prefer continuity: if this game already has an active indexed-upload session, reuse it.
    indexed_stmt = (
        select(Session)
        .join(RulesetMetadata, RulesetMetadata.session_id == Session.id)
        .where(
            Session.user_id == user["id"],
            Session.game_name == entry.game_name,
            Session.expires_at > now,
            RulesetMetadata.user_id == user["id"],
            RulesetMetadata.status == "INDEXED",
        )
        .order_by(Session.created_at.desc())
        .limit(1)
    )
    indexed_result = await db.execute(indexed_stmt)
    indexed_session = indexed_result.scalars().first()
    if indexed_session:
        entry.last_queried = now
        await db.commit()
        return SessionRead.model_validate(indexed_session)

    # Validate official rulesets linked in shelf entry.
    requested_official_ids = list(dict.fromkeys(entry.official_ruleset_ids or []))
    valid_official_ids: list[uuid.UUID] = []
    if requested_official_ids:
        valid_stmt = (
            select(OfficialRuleset.id)
            .where(
                OfficialRuleset.id.in_(requested_official_ids),
                OfficialRuleset.status.in_(READY_CATALOG_STATUSES),
                OfficialRuleset.publisher.has(Publisher.verified.is_(True)),
            )
        )
        valid_result = await db.execute(valid_stmt)
        valid_official_ids = [row[0] for row in valid_result.all()]

    # Reuse existing active session for this game if it already includes these official rulesets.
    if valid_official_ids:
        candidates_result = await db.execute(
            select(Session)
            .where(
                Session.user_id == user["id"],
                Session.game_name == entry.game_name,
                Session.expires_at > now,
            )
            .order_by(Session.created_at.desc())
            .limit(20)
        )
        required = set(valid_official_ids)
        for candidate in candidates_result.scalars().all():
            active_set = set(candidate.active_ruleset_ids or [])
            if required.issubset(active_set):
                entry.last_queried = now
                await db.commit()
                return SessionRead.model_validate(candidate)

    if not valid_official_ids:
        raise HTTPException(
            status_code=409,
            detail=(
                "No ready rules are linked to this shelf game yet. "
                "Upload and finish indexing a ruleset, or add a READY Armory title."
            ),
        )

    await limiter.check_and_increment(
        user_id=str(user["id"]),
        tier=user["tier"],
        category="session",
    )

    duration_hours = 24 if user["tier"] == "FREE" else 24 * 30
    new_session = Session(
        id=uuid.uuid4(),
        user_id=user["id"],
        game_name=entry.game_name,
        expires_at=now + timedelta(hours=duration_hours),
        active_ruleset_ids=valid_official_ids,
    )
    db.add(new_session)
    entry.last_queried = now
    await db.flush()
    await db.refresh(new_session)
    await db.commit()

    logger.info(
        "library_session_created",
        user_id=str(user["id"]),
        entry_id=str(entry.id),
        session_id=str(new_session.id),
        game_name=entry.game_name,
    )
    return SessionRead.model_validate(new_session)
