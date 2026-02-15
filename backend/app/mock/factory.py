"""factory.py — On-demand mock object factory for Arbiter AI.

Generates new mock objects with realistic data for dynamic endpoints
(e.g., POST /sessions, POST /judge). Unlike fixtures.py which holds
static data, factory functions create fresh objects per call.

Called by: mock_routes.py (for POST/PUT endpoints that create objects)
Depends on: fixtures.py (for default values and UUID helpers)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.mock.fixtures import MOCK_CURRENT_USER, _iso

# ─── Canned Verdicts ──────────────────────────────────────────────────────────
# WHY: A selection of realistic verdict responses keyed by keyword.
# When the mock LLM receives a query, it checks for keyword matches
# and returns the most relevant canned verdict. This makes demos
# feel realistic without any actual LLM calls.

_CANNED_VERDICTS: dict[str, dict[str, Any]] = {
    "default": {
        "verdict": (
            "Based on the official rules, the answer depends on the specific "
            "edition and any house rules your group uses. The core rulebook "
            "states that this is generally permitted unless a specific exception "
            "applies. Check the relevant section for your edition."
        ),
        "confidence": 0.75,
        "reasoning_chain": (
            "1. Searched the uploaded rulebook for relevant passages. "
            "2. Found applicable rules in the core mechanics section. "
            "3. Cross-referenced with FAQ and errata. "
            "4. No conflicts detected between sources."
        ),
        "follow_up_hint": "Try asking about a more specific rule for a detailed answer.",
    },
    "attack": {
        "verdict": (
            "An attack action follows the standard attack resolution procedure: "
            "roll to hit (d20 + modifiers vs AC/DC), then roll damage if successful. "
            "Special attack types may have additional steps or restrictions."
        ),
        "confidence": 0.92,
        "reasoning_chain": (
            "1. Located attack resolution rules in Chapter 9: Combat. "
            "2. Standard attack roll = d20 + ability modifier + proficiency bonus. "
            "3. Hit if roll meets or exceeds target's AC."
        ),
        "follow_up_hint": "Ask about specific attack types like opportunity attacks or grappling.",
    },
    "movement": {
        "verdict": (
            "Movement speed determines how far a character or piece can move "
            "in a single turn. Difficult terrain typically costs double movement. "
            "Some abilities grant bonus movement or allow disengaging without penalty."
        ),
        "confidence": 0.89,
        "reasoning_chain": (
            "1. Movement is measured in feet/squares/hexes depending on the game. "
            "2. Standard movement uses the character's speed stat. "
            "3. Difficult terrain doubles the movement cost."
        ),
        "follow_up_hint": "Ask about specific movement abilities or terrain effects.",
    },
    "trade": {
        "verdict": (
            "Trading follows the game's resource exchange rules. Most games "
            "allow trading between players during active turns, with the bank "
            "offering fixed exchange rates. Some games restrict trading to "
            "specific phases or conditions."
        ),
        "confidence": 0.87,
        "reasoning_chain": (
            "1. Trading rules vary by game but share common patterns. "
            "2. Player-to-player trades typically require mutual agreement. "
            "3. Bank trading uses fixed ratios (often 4:1 or better with ports/markets)."
        ),
        "follow_up_hint": "Ask about specific trade restrictions or port/market bonuses.",
    },
}


def create_mock_verdict(query: str, session_id: str | None = None) -> dict[str, Any]:
    """Generate a realistic mock verdict response for a given query.

    Used by POST /judge to return a canned verdict without calling any LLM.
    Matches query keywords to canned verdicts for realistic responses.

    Args:
        query: The user's rules question.
        session_id: Optional session UUID for the query_id.

    Returns:
        Dict matching the JudgeVerdict schema with verdict, confidence,
        citations, reasoning chain, and follow-up hint.
    """
    query_lower = query.lower()
    query_id = str(uuid.uuid4())

    # WHY: Match query keywords to canned verdicts for variety.
    # Falls back to "default" if no keywords match.
    matched = _CANNED_VERDICTS["default"]
    for keyword, verdict_data in _CANNED_VERDICTS.items():
        if keyword != "default" and keyword in query_lower:
            matched = verdict_data
            break

    return {
        "query_id": query_id,
        "verdict": matched["verdict"],
        "confidence": matched["confidence"],
        "reasoning_chain": matched["reasoning_chain"],
        "citations": [
            {
                "source": "Official Rulebook",
                "page": 42,
                "section": "Core Rules",
                "snippet": (
                    f"(Mock citation for query: '{query[:50]}...')"
                    if len(query) > 50
                    else f"(Mock citation for query: '{query}')"
                ),
                "is_official": True,
            },
        ],
        "conflicts": None,
        "follow_up_hint": matched["follow_up_hint"],
        "model": "mock-llm-v1",
    }


def create_mock_session(game_name: str) -> dict[str, Any]:
    """Generate a new mock session for the given game.

    Args:
        game_name: Human-readable game name (e.g., 'Catan').

    Returns:
        Dict matching the SessionRead schema with fresh UUID and timestamps.
    """
    now = datetime.now(UTC)
    return {
        "id": str(uuid.uuid4()),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": game_name,
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=30)),
    }


def create_mock_user(tier: str = "FREE") -> dict[str, Any]:
    """Generate a new mock user at the specified tier.

    Args:
        tier: Subscription tier — 'FREE' or 'PRO'.

    Returns:
        Dict matching the user context shape from deps.py.
    """
    user_id = str(uuid.uuid4())
    return {
        "id": user_id,
        "email": f"mock-{user_id[:8]}@arbiter.local",
        "name": f"Mock User ({tier})",
        "role": "USER",
        "tier": tier,
        "default_ruling_privacy": "PRIVATE",
    }


def create_mock_library_entry(game_name: str, game_slug: str | None = None) -> dict[str, Any]:
    """Generate a new library entry for the given game.

    Args:
        game_name: Display name (e.g., 'Spirit Island').
        game_slug: URL-safe slug. Auto-generated from game_name if not provided.

    Returns:
        Dict matching the LibraryEntryResponse schema.
    """
    now = datetime.now(UTC)
    slug = game_slug or game_name.lower().replace(" ", "-").replace("'", "")
    return {
        "id": str(uuid.uuid4()),
        "game_name": game_name,
        "game_slug": slug,
        "added_from_catalog": False,
        "official_ruleset_id": None,
        "is_favorite": False,
        "favorite": False,
        "last_queried": None,
        "created_at": _iso(now),
    }


def create_mock_ruling(
    query: str,
    game_name: str = "Unknown Game",
    privacy_level: str = "PRIVATE",
) -> dict[str, Any]:
    """Generate a new saved ruling with a mock verdict.

    Args:
        query: The user's rules question.
        game_name: Game this ruling belongs to.
        privacy_level: PRIVATE, PARTY, or PUBLIC.

    Returns:
        Dict matching the SavedRulingResponse schema.
    """
    now = datetime.now(UTC)
    verdict = create_mock_verdict(query)
    return {
        "id": str(uuid.uuid4()),
        "query": query,
        "verdict_json": verdict,
        "game_name": game_name,
        "session_id": None,
        "privacy_level": privacy_level,
        "tags": [],
        "created_at": _iso(now),
    }


def create_deterministic_vector(text: str, dimensions: int = 1024) -> list[float]:
    """Generate a deterministic pseudo-random vector from a text string.

    WHY: Mock embeddings need to be:
      1. Deterministic (same text → same vector) for test reproducibility
      2. Realistic dimensionality (1024 to match Titan embed)
      3. Normalized (unit length) to mimic real embeddings

    Args:
        text: Input text to embed.
        dimensions: Vector dimensionality (default 1024).

    Returns:
        List of floats representing the mock embedding vector.
    """
    # WHY: Using SHA-256 hash as seed ensures deterministic output that
    # looks random. We expand the hash to fill the target dimensions.
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    vector = []
    for i in range(dimensions):
        # Cycle through hash characters to create values in [-1, 1]
        char_idx = i % len(text_hash)
        raw = int(text_hash[char_idx], 16) / 15.0  # 0.0 to 1.0
        vector.append(raw * 2 - 1)  # Scale to [-1, 1]

    # L2-normalize for unit vectors
    magnitude = sum(v * v for v in vector) ** 0.5
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    return vector
