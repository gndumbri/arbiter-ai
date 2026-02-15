"""mock_routes.py — Complete mock API that mirrors all real endpoints.

Returns fixture data for every endpoint without touching the database,
external APIs, or authentication. Used when APP_MODE=mock.

Design principles:
    - Same URL paths as real routes (frontend needs zero changes)
    - Response shapes match real endpoint schemas exactly
    - No auth required (mock user is hardcoded)
    - No DB queries (all data from fixtures.py)
    - Supports basic CRUD illusion (POST returns new objects)
    - Every endpoint is documented with the same docstring style

Called by: main.py (conditionally mounted when APP_MODE=mock)
Depends on: mock/fixtures.py, mock/factory.py, core/environment.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.environment import get_environment_info, to_dict
from app.mock.factory import (
    create_mock_library_entry,
    create_mock_ruling,
    create_mock_session,
    create_mock_verdict,
)
from app.mock.fixtures import (
    MOCK_AGENTS,
    MOCK_CATALOG,
    MOCK_CURRENT_USER,
    MOCK_LIBRARY,
    MOCK_PARTIES,
    MOCK_PARTY_MEMBERS,
    MOCK_RULESETS,
    MOCK_RULING_GAMES,
    MOCK_RULINGS,
    MOCK_SESSIONS,
    MOCK_SUBSCRIPTION,
    MOCK_TIERS,
    MOCK_USERS,
)

logger = logging.getLogger(__name__)

MOCK_LIBRARY_STATE = [dict(entry) for entry in MOCK_LIBRARY]
MOCK_PARTY_MEMBERS_STATE = {
    party_id: [dict(member) for member in members]
    for party_id, members in MOCK_PARTY_MEMBERS.items()
}


def _lookup_mock_user(user_id: str) -> dict[str, Any] | None:
    """Return a fixture user by ID, if present."""
    for user in MOCK_USERS.values():
        if user["id"] == user_id:
            return user
    return None


# ─── Request Schemas ──────────────────────────────────────────────────────────
# WHY: Lightweight request schemas for POST endpoints. These match the
# real schemas but don't import from models/schemas.py to keep the
# mock module self-contained and avoid circular imports.


class MockSessionCreate(BaseModel):
    """Create session request."""
    game_name: str
    persona: str | None = None
    system_prompt_override: str | None = None


class MockJudgeQuery(BaseModel):
    """Judge query request."""
    session_id: str
    query: str
    game_name: str | None = None
    ruleset_ids: list[str] | None = None


class MockFeedbackRequest(BaseModel):
    """Feedback request (up/down)."""
    feedback: str


class MockLibraryAddGame(BaseModel):
    """Add game to library."""
    game_name: str
    game_slug: str | None = None
    official_ruleset_id: str | None = None


class MockRulingSave(BaseModel):
    """Save a ruling."""
    query: str
    verdict_json: dict[str, Any]
    game_name: str
    session_id: str | None = None
    privacy_level: str = "PRIVATE"
    tags: list[str] | None = None


# ─── Router Setup ─────────────────────────────────────────────────────────────
# WHY: We create two routers — one for /api/v1 prefixed routes and one
# for root-level routes (like /health). Both are exported for main.py.

router = APIRouter()
api_router = APIRouter(prefix="/api/v1")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/health", tags=["health"])
async def mock_health():
    """Health check — always healthy in mock mode.

    Returns environment info alongside the standard health fields
    so the frontend can detect which mode is active.

    Returns:
        Dict with status, database, redis, version, mode, and features.
    """
    env_info = get_environment_info()
    return {
        "status": "healthy",
        "database": "mock (in-memory)",
        "redis": "mock (in-memory)",
        "version": env_info.version,
        "mode": env_info.mode,
        "environment": to_dict(env_info),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/users/me", tags=["users"])
async def mock_get_current_user():
    """Return the hardcoded mock user profile.

    Auth: Bypassed (always returns the mock pro user).

    Returns:
        Mock user dict with id, email, name, role, tier.
    """
    logger.debug("Mock: GET /users/me → returning mock user '%s'", MOCK_CURRENT_USER["email"])
    return MOCK_CURRENT_USER


@api_router.get("/users/me/settings", tags=["users"])
async def mock_get_user_settings():
    """Return mock user settings.

    Returns:
        Dict with user preferences (default_ruling_privacy, email_notifications).
    """
    return {
        "default_ruling_privacy": MOCK_CURRENT_USER.get("default_ruling_privacy", "PRIVATE"),
        "email_notifications_enabled": True,
        "preferred_persona": "Standard Judge",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/sessions", tags=["sessions"])
async def mock_list_sessions(
    persona_only: bool = False,
    active_only: bool = False,
):
    """List mock sessions.

    Args:
        persona_only: If True, only sessions with a persona (agents).
        active_only: If True, exclude expired sessions.

    Returns:
        List of mock session dicts.
    """
    sessions = MOCK_SESSIONS
    if active_only:
        sessions = [s for s in sessions if "expired" not in s.get("expires_at", "")]
    logger.debug("Mock: GET /sessions → returning %d sessions", len(sessions))
    return sessions


@api_router.post("/sessions", status_code=201, tags=["sessions"])
async def mock_create_session(body: MockSessionCreate):
    """Create a new mock session.

    Args:
        body: MockSessionCreate with game_name.

    Returns:
        A freshly generated mock session dict.
    """
    session = create_mock_session(body.game_name)
    logger.info("Mock: POST /sessions → created session for '%s'", body.game_name)
    return session


# ═══════════════════════════════════════════════════════════════════════════════
# JUDGE (Adjudication)
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.post("/judge", tags=["judge"])
async def mock_judge_query(body: MockJudgeQuery):
    """Return a canned verdict for a rules question.

    Keyword-matches the query to pre-written verdicts for realistic
    responses. No LLM is called.

    Args:
        body: MockJudgeQuery with session_id and query text.

    Returns:
        Dict matching the JudgeVerdict schema.
    """
    verdict = create_mock_verdict(body.query, body.session_id)
    logger.info(
        "Mock: POST /judge → verdict for query='%s' (confidence=%.2f)",
        body.query[:50],
        verdict["confidence"],
    )
    return verdict


@api_router.post("/judge/{query_id}/feedback", tags=["judge"])
async def mock_judge_feedback(query_id: str, body: MockFeedbackRequest):
    """Accept feedback on a mock verdict.

    Logs the feedback but doesn't persist anything.

    Args:
        query_id: The verdict's query_id.
        body: MockFeedbackRequest with 'up' or 'down'.

    Returns:
        Confirmation dict.
    """
    logger.info("Mock: POST /judge/%s/feedback → %s", query_id, body.feedback)
    return {"status": "recorded", "query_id": query_id, "feedback": body.feedback}


# ═══════════════════════════════════════════════════════════════════════════════
# CATALOG
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/catalog/", tags=["catalog"])
async def mock_list_catalog(
    search: str | None = Query(None, description="Filter by game name or publisher"),
):
    """List mock catalog entries.

    Args:
        search: Optional text filter (case-insensitive substring match).

    Returns:
        List of mock catalog entry dicts.
    """
    entries = MOCK_CATALOG
    if search:
        term = search.lower()
        entries = [
            e for e in entries
            if term in e["game_name"].lower()
            or term in e.get("publisher_name", "").lower()
        ]
    logger.debug("Mock: GET /catalog/ → returning %d entries (search=%s)", len(entries), search)
    return entries


@api_router.get("/catalog/{game_slug}", tags=["catalog"])
async def mock_get_catalog_detail(game_slug: str):
    """Get a single mock catalog entry by slug.

    Args:
        game_slug: URL-safe game identifier.

    Returns:
        Mock catalog entry dict with extra detail fields.

    Raises:
        HTTPException: 404 if slug not found.
    """
    for entry in MOCK_CATALOG:
        if entry.get("game_slug") == game_slug:
            return {
                **entry,
                "chunk_count": 250,
                "pinecone_namespace": f"mock-{game_slug}",
            }
    raise HTTPException(status_code=404, detail=f"Game '{game_slug}' not found in mock catalog.")


# ═══════════════════════════════════════════════════════════════════════════════
# LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/library", tags=["library"])
async def mock_list_library():
    """List the mock user's game library.

    Returns:
        List of mock library entry dicts.
    """
    logger.debug("Mock: GET /library → returning %d entries", len(MOCK_LIBRARY_STATE))
    return MOCK_LIBRARY_STATE


@api_router.post("/library", status_code=201, tags=["library"])
async def mock_add_to_library(body: MockLibraryAddGame):
    """Add a game to the mock library.

    Args:
        body: MockLibraryAddGame with game_name.

    Returns:
        A freshly generated library entry dict.
    """
    existing = next(
        (
            entry
            for entry in MOCK_LIBRARY_STATE
            if entry["game_name"].strip().lower() == body.game_name.strip().lower()
        ),
        None,
    )
    if existing:
        raise HTTPException(status_code=409, detail="This game is already in your library.")

    entry = create_mock_library_entry(body.game_name, body.game_slug)
    if body.official_ruleset_id:
        entry["official_ruleset_id"] = body.official_ruleset_id
        entry["added_from_catalog"] = True

    MOCK_LIBRARY_STATE.insert(0, entry)
    logger.info("Mock: POST /library → added '%s'", body.game_name)
    return entry


@api_router.delete("/library/{entry_id}", tags=["library"])
async def mock_remove_from_library(entry_id: str):
    """Remove a game from the mock library.

    Args:
        entry_id: UUID of the library entry to remove.

    Returns:
        Confirmation dict.
    """
    for idx, entry in enumerate(MOCK_LIBRARY_STATE):
        if entry["id"] == entry_id:
            del MOCK_LIBRARY_STATE[idx]
            logger.info("Mock: DELETE /library/%s → removed", entry_id)
            return {"status": "deleted", "id": entry_id}
    raise HTTPException(status_code=404, detail="Library entry not found.")


@api_router.patch("/library/{entry_id}/favorite", tags=["library"])
async def mock_toggle_favorite(entry_id: str):
    """Toggle favorite status for a library entry.

    Args:
        entry_id: UUID of the library entry.

    Returns:
        Confirmation with new favorite status.
    """
    for entry in MOCK_LIBRARY_STATE:
        if entry["id"] == entry_id:
            next_value = not bool(entry.get("favorite"))
            entry["favorite"] = next_value
            entry["is_favorite"] = next_value
            logger.info("Mock: PATCH /library/%s/favorite → toggled", entry_id)
            return {"id": entry_id, "favorite": next_value}
    raise HTTPException(status_code=404, detail="Library entry not found.")


# ═══════════════════════════════════════════════════════════════════════════════
# RULINGS
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/rulings", tags=["rulings"])
async def mock_list_rulings(
    game_name: str | None = None,
    privacy: str | None = None,
):
    """List mock saved rulings.

    Args:
        game_name: Filter by game name.
        privacy: Filter by privacy level (PRIVATE, PARTY, PUBLIC).

    Returns:
        List of mock ruling dicts.
    """
    rulings = MOCK_RULINGS
    if game_name:
        rulings = [r for r in rulings if r["game_name"] == game_name]
    if privacy:
        rulings = [r for r in rulings if r["privacy_level"] == privacy]
    logger.debug("Mock: GET /rulings → returning %d rulings", len(rulings))
    return rulings


@api_router.get("/rulings/games", tags=["rulings"])
async def mock_ruling_games():
    """List games with saved rulings and their counts.

    Returns:
        List of {game_name, count} dicts.
    """
    return MOCK_RULING_GAMES


@api_router.post("/rulings", status_code=201, tags=["rulings"])
async def mock_save_ruling(body: MockRulingSave):
    """Save a new mock ruling.

    Args:
        body: MockRulingSave with query, verdict, game, privacy.

    Returns:
        A freshly generated ruling dict.
    """
    ruling = create_mock_ruling(body.query, body.game_name, body.privacy_level)
    logger.info("Mock: POST /rulings → saved ruling for '%s'", body.game_name)
    return ruling


@api_router.get("/rulings/{ruling_id}", tags=["rulings"])
async def mock_get_ruling(ruling_id: str):
    """Get a single mock ruling by ID.

    Args:
        ruling_id: UUID of the ruling.

    Returns:
        Mock ruling dict.

    Raises:
        HTTPException: 404 if not found.
    """
    for ruling in MOCK_RULINGS:
        if ruling["id"] == ruling_id:
            return ruling
    raise HTTPException(status_code=404, detail="Ruling not found in mock data.")


@api_router.delete("/rulings/{ruling_id}", tags=["rulings"])
async def mock_delete_ruling(ruling_id: str):
    """Delete a mock ruling.

    Args:
        ruling_id: UUID of the ruling to delete.

    Returns:
        Confirmation dict.
    """
    logger.info("Mock: DELETE /rulings/%s → deleted", ruling_id)
    return {"status": "deleted", "id": ruling_id}


# ═══════════════════════════════════════════════════════════════════════════════
# PARTIES
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/parties", tags=["parties"])
async def mock_list_parties():
    """List mock parties.

    Returns:
        List of mock party dicts.
    """
    logger.debug("Mock: GET /parties → returning %d parties", len(MOCK_PARTIES))
    return MOCK_PARTIES


@api_router.get("/parties/{party_id}", tags=["parties"])
async def mock_get_party(party_id: str):
    """Get a single mock party with member list.

    Args:
        party_id: UUID of the party.

    Returns:
        Mock party dict with members array.

    Raises:
        HTTPException: 404 if not found.
    """
    for party in MOCK_PARTIES:
        if party["id"] == party_id:
            members = MOCK_PARTY_MEMBERS_STATE.get(party_id, [])
            return {**party, "members": members}
    raise HTTPException(status_code=404, detail="Party not found in mock data.")


@api_router.get("/parties/{party_id}/members", tags=["parties"])
async def mock_list_party_members(party_id: str):
    """List members for a mock party with names/emails for UI display."""
    members = MOCK_PARTY_MEMBERS_STATE.get(party_id)
    if members is None:
        raise HTTPException(status_code=404, detail="Party not found in mock data.")

    # Match real route behavior: only members can view this list.
    if not any(m["user_id"] == MOCK_CURRENT_USER["id"] for m in members):
        raise HTTPException(status_code=403, detail="Not a member of this party")

    enriched = []
    for member in members:
        user = _lookup_mock_user(member["user_id"])
        enriched.append(
            {
                "user_id": member["user_id"],
                "user_name": user.get("name") if user else None,
                "user_email": user.get("email") if user else None,
                "role": member["role"],
                "joined_at": member.get("joined_at"),
            }
        )
    return enriched


# ═══════════════════════════════════════════════════════════════════════════════
# BILLING
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/billing/subscription", tags=["billing"])
async def mock_get_subscription():
    """Return mock subscription status.

    Returns:
        Mock subscription dict (always PRO tier, active).
    """
    return MOCK_SUBSCRIPTION


@api_router.get("/billing/tiers", tags=["billing"])
async def mock_list_tiers():
    """List mock subscription tiers.

    Returns:
        List of tier dicts with names and limits.
    """
    return MOCK_TIERS


@api_router.post("/billing/checkout", tags=["billing"])
async def mock_create_checkout():
    """Simulate Stripe checkout session creation.

    Returns:
        Mock checkout URL (doesn't actually redirect to Stripe).
    """
    logger.info("Mock: POST /billing/checkout → returning mock checkout URL")
    return {
        "checkout_url": "https://checkout.stripe.com/mock-session",
        "session_id": "cs_mock_123456",
    }


@api_router.post("/billing/portal", tags=["billing"])
async def mock_create_portal():
    """Simulate Stripe billing portal session.

    Returns:
        Mock portal URL.
    """
    return {
        "portal_url": "https://billing.stripe.com/mock-portal",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTS
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/agents", tags=["agents"])
async def mock_list_agents():
    """List mock agents (persona-based sessions).

    Returns:
        List of mock agent dicts.
    """
    logger.debug("Mock: GET /agents → returning %d agents", len(MOCK_AGENTS))
    return MOCK_AGENTS


# ═══════════════════════════════════════════════════════════════════════════════
# RULESETS (Session-level)
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/sessions/{session_id}/rulesets", tags=["sessions"])
async def mock_list_session_rulesets(session_id: str):
    """List rulesets attached to a mock session.

    Args:
        session_id: UUID of the session.

    Returns:
        List of mock ruleset dicts filtered by session_id.
    """
    rulesets = [r for r in MOCK_RULESETS if r.get("session_id") == session_id]
    return rulesets


@api_router.post("/sessions/{session_id}/rulesets", status_code=202, tags=["sessions"])
@api_router.post("/sessions/{session_id}/rulesets/upload", status_code=202, tags=["sessions"])
async def mock_upload_ruleset(session_id: str):
    """Simulate ruleset upload (returns a mock ruleset).

    Args:
        session_id: UUID of the session.

    Returns:
        Mock ruleset dict with PROCESSING status.
    """
    import uuid as _uuid_mod

    logger.info("Mock: POST /sessions/%s/rulesets/upload → simulated", session_id)
    ruleset_id = str(_uuid_mod.uuid4())
    return {
        "ruleset_id": ruleset_id,
        "status": "PROCESSING",
        "chunk_count": 0,
        "message": "Ruleset processing started. Check status endpoint for updates.",
    }


# Global ruleset list (matches real /api/v1/rulesets)
@api_router.get("/rulesets", tags=["sessions"])
async def mock_list_rulesets():
    """List all mock rulesets (global endpoint)."""
    return MOCK_RULESETS


@api_router.get("/rulesets/{ruleset_id}/status", tags=["sessions"])
async def mock_ruleset_status(ruleset_id: str):
    """Get status for a mock ruleset by ID."""
    for ruleset in MOCK_RULESETS:
        if ruleset.get("id") == ruleset_id:
            return {
                "ruleset_id": ruleset["id"],
                "status": ruleset.get("status", "INDEXED"),
                "game_name": ruleset.get("game_name", "Unknown"),
                "source_type": ruleset.get("source_type", "BASE"),
                "chunk_count": ruleset.get("chunk_count", 0),
                "created_at": ruleset.get("created_at"),
            }
    raise HTTPException(status_code=404, detail="Ruleset not found")


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT INFO
# ═══════════════════════════════════════════════════════════════════════════════


@api_router.get("/environment", tags=["system"])
async def mock_environment_info():
    """Return current environment configuration.

    Used by the frontend EnvironmentBadge component to detect
    which mode is active.

    Returns:
        Dict with mode, app_env, version, and feature flags.
    """
    return to_dict(get_environment_info())
