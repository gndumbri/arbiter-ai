"""Session management endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter

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
    """Create a new game session."""
    # Determine session duration based on tier
    duration_hours = 24 if user["tier"] == "FREE" else 24 * 30

    session = Session(
        id=uuid.uuid4(),
        user_id=user["id"],
        game_name=body.game_name,
        expires_at=datetime.now(UTC) + timedelta(hours=duration_hours),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    logger.info(
        "session_created",
        session_id=str(session.id),
        user_id=str(user["id"]),
        game_name=body.game_name,
    )
    return SessionRead.model_validate(session)
