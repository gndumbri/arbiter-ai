"""agents.py — Manage 'Agents' (Persona-based Sessions).

Agents are Sessions that act as configured game-specific judges.
Every Session with a game_name is treated as an agent. In the future,
sessions may have an explicit `persona` column to distinguish
between casual queries and configured agents.

Endpoints:
    GET /api/v1/agents  → List all sessions as agents

Called by: Frontend dashboard "My Agents" page.
Depends on: deps.py (CurrentUser, DbSession), tables.py (Session)
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from sqlalchemy import desc, select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import Session

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("")
async def list_agents(user: CurrentUser, db: DbSession):
    """List sessions that act as configured agents.

    WHY: The frontend "My Agents" page needs a dedicated view of sessions
    enriched with agent-specific metadata (persona, active state).
    We treat any session with a game_name as an agent for now.

    Auth: JWT required.
    Returns: List of agent objects with persona info.
    """
    stmt = (
        select(Session)
        .where(Session.user_id == user["id"])
        .order_by(desc(Session.created_at))
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    now = datetime.now(UTC)

    return [
        {
            "id": str(s.id),
            "game_name": s.game_name,
            "persona": s.persona,
            "system_prompt_override": s.system_prompt_override,
            "created_at": s.created_at.isoformat(),
            "active_ruleset_ids": (
                [str(rid) for rid in s.active_ruleset_ids]
                if s.active_ruleset_ids
                else None
            ),
            "active": s.expires_at is not None and s.expires_at > now,
        }
        for s in sessions
    ]
