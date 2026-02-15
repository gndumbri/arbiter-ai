"""fixtures.py — Rich, realistic fake data for every Arbiter AI entity.

All mock API routes return data from this module. Data is designed to be
realistic enough for demos, UI testing, and frontend development.

Design principles:
    - Deterministic UUIDs so data is reproducible across restarts
    - Realistic game names, verdicts, and citations
    - Covers edge cases (expired sessions, empty libraries, etc.)
    - Zero external dependencies

Called by: mock_routes.py, factory.py
Depends on: Nothing
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# ─── Deterministic UUIDs ─────────────────────────────────────────────────────
# WHY: Using deterministic UUIDs (not random) so that:
#   1. Mock data is stable across server restarts
#   2. Frontend can hardcode IDs in tests
#   3. Cross-entity references (e.g., user_id in sessions) are consistent

_UUID_NS = "00000000-0000-4000-a000-"  # Prefix for all mock UUIDs


def _uuid(suffix: str) -> str:
    """Generate a deterministic mock UUID.

    Args:
        suffix: 12-char hex string appended to the UUID namespace.

    Returns:
        A valid UUID string like '00000000-0000-4000-a000-000000000001'.
    """
    return f"{_UUID_NS}{suffix.zfill(12)}"


# ─── Timestamps ──────────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)
_YESTERDAY = _NOW - timedelta(days=1)
_LAST_WEEK = _NOW - timedelta(weeks=1)
_NEXT_MONTH = _NOW + timedelta(days=30)
_EXPIRED = _NOW - timedelta(hours=1)


def _iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 string."""
    return dt.isoformat()


# ─── Users ────────────────────────────────────────────────────────────────────
# WHY: Three users at different tiers to test tier-gated features
# (rate limits, session duration, billing UI).

MOCK_USERS = {
    "free": {
        "id": _uuid("1"),
        "email": "frodo@shire.local",
        "name": "Frodo Baggins",
        "role": "USER",
        "tier": "FREE",
        "default_ruling_privacy": "PRIVATE",
    },
    "pro": {
        "id": _uuid("2"),
        "email": "gandalf@moria.local",
        "name": "Gandalf the Grey",
        "role": "USER",
        "tier": "PRO",
        "default_ruling_privacy": "PARTY",
    },
    "admin": {
        "id": _uuid("3"),
        "email": "admin@arbiter.local",
        "name": "Arbiter Admin",
        "role": "ADMIN",
        "tier": "PRO",
        "default_ruling_privacy": "PUBLIC",
    },
}

# Default mock user for auth bypass
MOCK_CURRENT_USER = MOCK_USERS["pro"]

# ─── Sessions ─────────────────────────────────────────────────────────────────
# WHY: Multiple sessions across popular board games so the UI always
# has data to render. Includes one expired session for edge-case testing.

MOCK_SESSIONS = [
    {
        "id": _uuid("100"),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": "Dungeons & Dragons 5th Edition",
        "created_at": _iso(_LAST_WEEK),
        "expires_at": _iso(_NEXT_MONTH),
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "active_ruleset_ids": [_uuid("500"), _uuid("501")],
    },
    {
        "id": _uuid("101"),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": "Catan",
        "created_at": _iso(_YESTERDAY),
        "expires_at": _iso(_NEXT_MONTH),
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "active_ruleset_ids": [_uuid("502")],
    },
    {
        "id": _uuid("102"),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": "Wingspan",
        "created_at": _iso(_YESTERDAY),
        "expires_at": _iso(_NEXT_MONTH),
        "persona": "Bird Enthusiast Judge",
        "system_prompt_override": None,
        "active_ruleset_ids": [_uuid("503")],
    },
    {
        "id": _uuid("103"),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": "Gloomhaven",
        "created_at": _iso(_LAST_WEEK),
        "expires_at": _iso(_NEXT_MONTH),
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "active_ruleset_ids": [],
    },
    {
        # WHY: Expired session tests the 410 Gone UI path
        "id": _uuid("104"),
        "user_id": MOCK_CURRENT_USER["id"],
        "game_name": "Ticket to Ride",
        "created_at": _iso(_LAST_WEEK),
        "expires_at": _iso(_EXPIRED),
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "active_ruleset_ids": [],
    },
]

# ─── Catalog ──────────────────────────────────────────────────────────────────
# WHY: Realistic catalog entries mimic what publishers would push.
# Covers a variety of game types, publishers, and statuses.

MOCK_CATALOG = [
    {
        "id": _uuid("200"),
        "game_name": "Dungeons & Dragons 5th Edition",
        "game_slug": "dnd-5e",
        "publisher_name": "Wizards of the Coast",
        "version": "2024",
        "status": "PUBLISHED",
        "license_type": "OGL 1.0a",
        "attribution_text": "© Wizards of the Coast LLC",
    },
    {
        "id": _uuid("201"),
        "game_name": "Catan",
        "game_slug": "catan",
        "publisher_name": "CATAN Studio",
        "version": "6th Edition",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("202"),
        "game_name": "Wingspan",
        "game_slug": "wingspan",
        "publisher_name": "Stonemaier Games",
        "version": "2nd Printing",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("203"),
        "game_name": "Gloomhaven",
        "game_slug": "gloomhaven",
        "publisher_name": "Cephalofair Games",
        "version": "2nd Edition",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("204"),
        "game_name": "Ticket to Ride",
        "game_slug": "ticket-to-ride",
        "publisher_name": "Days of Wonder",
        "version": "Original",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("205"),
        "game_name": "Pandemic",
        "game_slug": "pandemic",
        "publisher_name": "Z-Man Games",
        "version": "10th Anniversary",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("206"),
        "game_name": "Terraforming Mars",
        "game_slug": "terraforming-mars",
        "publisher_name": "FryxGames",
        "version": "1st Edition",
        "status": "PUBLISHED",
        "license_type": None,
        "attribution_text": None,
    },
    {
        "id": _uuid("207"),
        "game_name": "Spirit Island",
        "game_slug": "spirit-island",
        "publisher_name": "Greater Than Games",
        "version": "Definitive Edition",
        "status": "PENDING",
        "license_type": None,
        "attribution_text": None,
    },
]

# ─── Library ──────────────────────────────────────────────────────────────────
# WHY: The user's personal game library — includes favorites and
# last-queried timestamps for testing the library UI sorting.

MOCK_LIBRARY = [
    {
        "id": _uuid("300"),
        "game_name": "Dungeons & Dragons 5th Edition",
        "game_slug": "dnd-5e",
        "added_from_catalog": True,
        "official_ruleset_id": _uuid("200"),
        "is_favorite": True,
        "favorite": True,
        "last_queried": _iso(_YESTERDAY),
        "created_at": _iso(_LAST_WEEK),
    },
    {
        "id": _uuid("301"),
        "game_name": "Catan",
        "game_slug": "catan",
        "added_from_catalog": True,
        "official_ruleset_id": _uuid("201"),
        "is_favorite": True,
        "favorite": True,
        "last_queried": _iso(_YESTERDAY),
        "created_at": _iso(_LAST_WEEK),
    },
    {
        "id": _uuid("302"),
        "game_name": "Wingspan",
        "game_slug": "wingspan",
        "added_from_catalog": True,
        "official_ruleset_id": _uuid("202"),
        "is_favorite": False,
        "favorite": False,
        "last_queried": None,
        "created_at": _iso(_YESTERDAY),
    },
    {
        "id": _uuid("303"),
        "game_name": "Gloomhaven",
        "game_slug": "gloomhaven",
        "added_from_catalog": True,
        "official_ruleset_id": _uuid("203"),
        "is_favorite": False,
        "favorite": False,
        "last_queried": _iso(_LAST_WEEK),
        "created_at": _iso(_LAST_WEEK),
    },
]

# ─── Saved Rulings ────────────────────────────────────────────────────────────
# WHY: These test every privacy level (PRIVATE, PARTY, PUBLIC) and
# include realistic verdicts with citations and conflicts.

MOCK_RULINGS = [
    {
        "id": _uuid("400"),
        "query": "Can a rogue use Sneak Attack with a thrown dagger?",
        "verdict_json": {
            "query_id": _uuid("400"),
            "verdict": (
                "Yes. Sneak Attack requires a finesse or ranged weapon. "
                "A dagger has the finesse and thrown properties, so it qualifies "
                "for Sneak Attack whether used in melee or thrown."
            ),
            "confidence": 0.95,
            "reasoning_chain": (
                "1. Sneak Attack requires a finesse or ranged weapon (PHB p.96). "
                "2. A dagger has both the finesse and thrown properties (PHB p.149). "
                "3. The thrown property does not change the weapon's category. "
                "4. Therefore, a thrown dagger still qualifies for Sneak Attack."
            ),
            "citations": [
                {
                    "source": "Player's Handbook",
                    "page": 96,
                    "section": "Sneak Attack",
                    "snippet": "Beginning at 1st level, you know how to strike subtly and exploit a foe's distraction. Once per turn, you can deal an extra 1d6 damage to one creature you hit with an attack if you have advantage on the attack roll. The attack must use a finesse or a ranged weapon.",
                    "is_official": True,
                },
                {
                    "source": "Player's Handbook",
                    "page": 149,
                    "section": "Weapons — Dagger",
                    "snippet": "Dagger. Finesse, light, thrown (range 20/60). 1d4 piercing.",
                    "is_official": True,
                },
            ],
            "conflicts": None,
            "follow_up_hint": "You might also ask: Does the Extra Attack feature let you Sneak Attack twice?",
            "model": "mock-llm-v1",
        },
        "game_name": "Dungeons & Dragons 5th Edition",
        "session_id": _uuid("100"),
        "privacy_level": "PRIVATE",
        "tags": ["combat", "rogue", "sneak-attack"],
        "created_at": _iso(_YESTERDAY),
    },
    {
        "id": _uuid("401"),
        "query": "If I build a settlement on a port in Catan, do I get the trade bonus immediately?",
        "verdict_json": {
            "query_id": _uuid("401"),
            "verdict": (
                "Yes. As soon as you build a settlement on a harbor (port) "
                "intersection, you immediately gain the trade advantage. "
                "You can use it on your very next trade with the bank."
            ),
            "confidence": 0.92,
            "reasoning_chain": (
                "1. Harbors grant special trade ratios (Catan rules p.10). "
                "2. The bonus is tied to having a settlement/city on the harbor intersection. "
                "3. There is no waiting period — the benefit is immediate upon building."
            ),
            "citations": [
                {
                    "source": "Catan Rulebook",
                    "page": 10,
                    "section": "Maritime Trade",
                    "snippet": "If you have built a settlement or city on a harbor, you can trade with the bank more favorably.",
                    "is_official": True,
                },
            ],
            "conflicts": None,
            "follow_up_hint": "Related: Can you use a 2:1 port on the same turn you build the settlement?",
            "model": "mock-llm-v1",
        },
        "game_name": "Catan",
        "session_id": _uuid("101"),
        "privacy_level": "PUBLIC",
        "tags": ["trading", "ports", "settlements"],
        "created_at": _iso(_YESTERDAY),
    },
    {
        "id": _uuid("402"),
        "query": "Can birds with a 'when played' power activate that power if tucked under another bird?",
        "verdict_json": {
            "query_id": _uuid("402"),
            "verdict": (
                "No. When a bird card is tucked under another bird, it is not "
                "'played' — it is placed as a tucked card for points. Only birds "
                "placed into a habitat row trigger their 'when played' powers."
            ),
            "confidence": 0.97,
            "reasoning_chain": (
                "1. 'When played' powers trigger only when a bird is placed into your habitat. "
                "2. Tucking places a card face-down under another bird for end-of-round scoring. "
                "3. Tucked cards are not 'played' — they don't enter a habitat."
            ),
            "citations": [
                {
                    "source": "Wingspan Rulebook",
                    "page": 7,
                    "section": "Playing a Bird",
                    "snippet": "When you play a bird, place it in the leftmost open slot in one of your habitats. Then activate any 'when played' power on the bird.",
                    "is_official": True,
                },
            ],
            "conflicts": None,
            "follow_up_hint": None,
            "model": "mock-llm-v1",
        },
        "game_name": "Wingspan",
        "session_id": _uuid("102"),
        "privacy_level": "PARTY",
        "tags": ["bird-powers", "tucking"],
        "created_at": _iso(_LAST_WEEK),
    },
    {
        "id": _uuid("403"),
        "query": "In Gloomhaven, can you loot a treasure tile and then move away in the same turn?",
        "verdict_json": {
            "query_id": _uuid("403"),
            "verdict": (
                "Yes. Looting is not a separate action — if you end a movement on "
                "a treasure tile (or move through it with certain abilities), you loot it. "
                "If you still have movement remaining, you can continue moving."
            ),
            "confidence": 0.88,
            "reasoning_chain": (
                "1. Looting happens automatically when you enter a hex with treasure (FAQ). "
                "2. Movement continues if you have movement points remaining. "
                "3. Some abilities grant 'loot on move' which also doesn't stop movement."
            ),
            "citations": [
                {
                    "source": "Gloomhaven Rulebook",
                    "page": 23,
                    "section": "Looting",
                    "snippet": "Whenever a figure enters a hex with a money token or treasure tile, that figure automatically picks it up.",
                    "is_official": True,
                },
            ],
            "conflicts": [
                {
                    "description": "Some community interpretations suggest looting ends movement.",
                    "resolution": "The official FAQ confirms looting does not consume movement points.",
                },
            ],
            "follow_up_hint": "Follow-up: Does the Scoundrel's 'Loot 1' action let you pick up adjacent tokens?",
            "model": "mock-llm-v1",
        },
        "game_name": "Gloomhaven",
        "session_id": _uuid("103"),
        "privacy_level": "PUBLIC",
        "tags": ["looting", "movement"],
        "created_at": _iso(_LAST_WEEK),
    },
    {
        "id": _uuid("404"),
        "query": "Does the longest road in Catan count if it loops back on itself?",
        "verdict_json": {
            "query_id": _uuid("404"),
            "verdict": (
                "A road that loops back counts, but you cannot double-count "
                "road segments. The longest road is the longest continuous path "
                "of roads without reusing any segment."
            ),
            "confidence": 0.90,
            "reasoning_chain": (
                "1. Longest road = longest continuous path (no segment reuse). "
                "2. A loop is valid but each segment counts only once. "
                "3. Branches don't add to the count unless they extend the path."
            ),
            "citations": [
                {
                    "source": "Catan Rulebook",
                    "page": 12,
                    "section": "Longest Road",
                    "snippet": "The longest road is determined by counting the number of contiguous road segments.",
                    "is_official": True,
                },
            ],
            "conflicts": None,
            "follow_up_hint": None,
            "model": "mock-llm-v1",
        },
        "game_name": "Catan",
        "session_id": _uuid("101"),
        "privacy_level": "PRIVATE",
        "tags": ["longest-road"],
        "created_at": _iso(_YESTERDAY),
    },
    {
        "id": _uuid("405"),
        "query": "Can you claim 2 routes between the same cities in Ticket to Ride?",
        "verdict_json": {
            "query_id": _uuid("405"),
            "verdict": (
                "It depends on the number of players. In a 2-3 player game, "
                "only one of the double routes can be claimed. In 4+ player "
                "games, both routes can be claimed (but not by the same player)."
            ),
            "confidence": 0.94,
            "reasoning_chain": (
                "1. Double routes are two parallel routes between the same cities. "
                "2. In 2-3 player games, one route is blocked after the first is claimed. "
                "3. In 4-5 player games, both routes can be claimed by different players."
            ),
            "citations": [
                {
                    "source": "Ticket to Ride Rulebook",
                    "page": 5,
                    "section": "Double Routes",
                    "snippet": "In 2 or 3 player games, only one of the two routes can be used.",
                    "is_official": True,
                },
            ],
            "conflicts": None,
            "follow_up_hint": "Related: In Ticket to Ride Europe, do tunnels follow the same rules?",
            "model": "mock-llm-v1",
        },
        "game_name": "Ticket to Ride",
        "session_id": _uuid("104"),
        "privacy_level": "PUBLIC",
        "tags": ["routes", "double-routes"],
        "created_at": _iso(_LAST_WEEK),
    },
]

# ─── Ruling Games (aggregated counts) ────────────────────────────────────────

MOCK_RULING_GAMES = [
    {"game_name": "Catan", "count": 2},
    {"game_name": "Dungeons & Dragons 5th Edition", "count": 1},
    {"game_name": "Gloomhaven", "count": 1},
    {"game_name": "Ticket to Ride", "count": 1},
    {"game_name": "Wingspan", "count": 1},
]

# ─── Parties ──────────────────────────────────────────────────────────────────
# WHY: Two parties — one owned by the mock user, one where they're a member.
# Tests both the owner and member UI paths.

MOCK_PARTIES = [
    {
        "id": _uuid("600"),
        "name": "Game Night Crew",
        "owner_id": MOCK_CURRENT_USER["id"],
        "member_count": 4,
        "created_at": _iso(_LAST_WEEK),
    },
    {
        "id": _uuid("601"),
        "name": "Board Game Club",
        "owner_id": _uuid("1"),  # Owned by the free user
        "member_count": 7,
        "created_at": _iso(_LAST_WEEK),
    },
]

MOCK_PARTY_MEMBERS = {
    _uuid("600"): [
        {"user_id": MOCK_CURRENT_USER["id"], "role": "OWNER", "joined_at": _iso(_LAST_WEEK)},
        {"user_id": _uuid("1"), "role": "MEMBER", "joined_at": _iso(_LAST_WEEK)},
        {"user_id": _uuid("10"), "role": "MEMBER", "joined_at": _iso(_YESTERDAY)},
        {"user_id": _uuid("11"), "role": "MEMBER", "joined_at": _iso(_YESTERDAY)},
    ],
    _uuid("601"): [
        {"user_id": _uuid("1"), "role": "OWNER", "joined_at": _iso(_LAST_WEEK)},
        {"user_id": MOCK_CURRENT_USER["id"], "role": "MEMBER", "joined_at": _iso(_YESTERDAY)},
    ],
}

# ─── Subscriptions & Tiers ────────────────────────────────────────────────────

MOCK_SUBSCRIPTION = {
    "plan_tier": "PRO",
    "status": "active",
    "stripe_customer_id": "cus_mock_123456",
    "current_period_end": _iso(_NEXT_MONTH),
}

MOCK_TIERS = [
    {"name": "FREE", "daily_query_limit": 5, "stripe_product_id": None},
    {"name": "PRO", "daily_query_limit": 999, "stripe_product_id": "prod_mock_pro"},
]

# ─── Agents ───────────────────────────────────────────────────────────────────
# WHY: Agents are sessions with game context. Reuse session data
# but add agent-specific fields (persona, active state).

MOCK_AGENTS = [
    {
        "id": _uuid("100"),
        "game_name": "Dungeons & Dragons 5th Edition",
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "created_at": _iso(_LAST_WEEK),
        "active_ruleset_ids": [_uuid("500"), _uuid("501")],
        "active": True,
    },
    {
        "id": _uuid("101"),
        "game_name": "Catan",
        "persona": "Standard Judge",
        "system_prompt_override": None,
        "created_at": _iso(_YESTERDAY),
        "active_ruleset_ids": [_uuid("502")],
        "active": True,
    },
    {
        "id": _uuid("102"),
        "game_name": "Wingspan",
        "persona": "Bird Enthusiast Judge",
        "system_prompt_override": None,
        "created_at": _iso(_YESTERDAY),
        "active_ruleset_ids": [_uuid("503")],
        "active": True,
    },
]

# ─── Rulesets ─────────────────────────────────────────────────────────────────

MOCK_RULESETS = [
    {
        "id": _uuid("500"),
        "game_name": "Dungeons & Dragons 5th Edition",
        "status": "READY",
        "created_at": _iso(_LAST_WEEK),
        "chunk_count": 847,
        "filename": "dnd5e-phb.pdf",
        "session_id": _uuid("100"),
    },
    {
        "id": _uuid("501"),
        "game_name": "Dungeons & Dragons 5th Edition",
        "status": "READY",
        "created_at": _iso(_LAST_WEEK),
        "chunk_count": 412,
        "filename": "dnd5e-dmg.pdf",
        "session_id": _uuid("100"),
    },
    {
        "id": _uuid("502"),
        "game_name": "Catan",
        "status": "READY",
        "created_at": _iso(_YESTERDAY),
        "chunk_count": 156,
        "filename": "catan-rules.pdf",
        "session_id": _uuid("101"),
    },
    {
        "id": _uuid("503"),
        "game_name": "Wingspan",
        "status": "READY",
        "created_at": _iso(_YESTERDAY),
        "chunk_count": 203,
        "filename": "wingspan-rules.pdf",
        "session_id": _uuid("102"),
    },
]
