"""sessions.py — Game session CRUD endpoints.

Manages game sessions — each session groups uploaded rulesets and
queries for a specific game. Sessions have tier-based expiry
(24h for FREE, 30d for PRO users).

Endpoints:
    POST /api/v1/sessions    → Create a new session
    GET  /api/v1/sessions    → List user's sessions (active only by default)

Called by: Frontend dashboard (create session), ChatInterface (session context).
Depends on: deps.py (CurrentUser, DBSession),
            tables.py (Session),
            schemas.py (SessionCreate, SessionRead)

Architecture note for AI agents:
    Sessions are the top-level container for a user's interaction with
    Arbiter AI. Each session belongs to one game and holds multiple
    uploaded rulesets. The judge.py route validates session ownership
    and expiry before running adjudication. Expired sessions return
    410 Gone from the judge endpoint but still appear in the user's
    session list (marked as expired in the frontend).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.schemas import SessionCreate, SessionRead
from app.models.tables import Session

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=SessionRead, status_code=201)
async def create_session(
    body: SessionCreate,
    user: CurrentUser,
    db: DBSession,
) -> SessionRead:
    """Create a new game session.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers (session duration varies by tier).

    Args:
        body: SessionCreate with game_name, optional persona and system_prompt.

    Returns:
        The newly created session object.

    Note: Session duration is tier-based:
        - FREE users: 24-hour sessions
        - PRO/ADMIN users: 30-day sessions
    """
    # WHY: FREE users get shorter sessions to encourage upgrades,
    # PRO users get 30-day sessions for extended campaign play.
    duration_hours = 24 if user["tier"] == "FREE" else 24 * 30

    session = Session(
        id=uuid.uuid4(),
        user_id=user["id"],
        game_name=body.game_name,
        expires_at=datetime.now(UTC) + timedelta(hours=duration_hours),
        persona=body.persona,
        system_prompt_override=body.system_prompt_override,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    logger.info(
        "session_created",
        session_id=str(session.id),
        user_id=str(user["id"]),
        game_name=body.game_name,
        expires_in_hours=duration_hours,
    )
    return SessionRead.model_validate(session)


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(
    user: CurrentUser,
    db: DBSession,
    persona_only: bool = False,
    active_only: bool = False,
) -> list[SessionRead]:
    """List user sessions.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Args:
        persona_only: If True, only return sessions with a persona set.
                      Used by the Agents page to list saved agent configs.
        active_only: If True, exclude expired sessions. Useful for
                     showing only sessions the user can still query.

    Returns:
        List of sessions, ordered by most recent first.
    """
    stmt = select(Session).where(Session.user_id == user["id"])

    if persona_only:
        stmt = stmt.where(Session.persona.is_not(None))

    # WHY: active_only filters out expired sessions so the dashboard
    # only shows sessions the user can actually submit queries to.
    if active_only:
        stmt = stmt.where(Session.expires_at > datetime.now(UTC))

    stmt = stmt.order_by(Session.created_at.desc())
    result = await db.execute(stmt)
    return [SessionRead.model_validate(s) for s in result.scalars().all()]
