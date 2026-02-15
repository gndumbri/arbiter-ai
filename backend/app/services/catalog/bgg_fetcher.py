"""bgg_fetcher.py — Fetch metadata from BoardGameGeek.

LEGAL NOTE: We only fetch publicly available metadata (titles, ids, years).
No copyrighted rules content is downloaded or stored. Games are created with
status="UPLOAD_REQUIRED" so users must supply their own rulebooks.

Sources:
- BGG XML API v2 Hot list: https://boardgamegeek.com/xmlapi2/hot?type=boardgame
- BGG ranked browse pages: https://boardgamegeek.com/browse/boardgame/page/1
"""

from __future__ import annotations

import html
import math
import re
import time
import uuid

import requests
import structlog
from defusedxml import ElementTree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import OfficialRuleset

logger = structlog.get_logger()

BGG_HOT_URL = "https://boardgamegeek.com/xmlapi2/hot?type=boardgame"
BGG_THING_URL = "https://boardgamegeek.com/xmlapi2/thing"
BGG_BROWSE_URL = "https://boardgamegeek.com/browse/boardgame/page/{page}"

# Rate-limit delay between BGG requests (seconds)
_REQUEST_DELAY = 6
_RANKED_REQUEST_DELAY = 1.5
_RANKED_GAMES_PER_PAGE = 100
_MAX_RANKED_LIMIT = 2000

_BROWSE_ROW_PATTERN = re.compile(
    r'href="/boardgame/(?P<bgg_id>\d+)/[^"]+"\s+class=[\'"]primary[\'"]\s*>'
    r"(?P<name>[^<]+)</a>",
    re.IGNORECASE,
)


def _slugify(name: str) -> str:
    """Convert a game name to a URL-safe slug.

    Examples:
        "Catan: Starfarers" → "catan-starfarers"
        "7 Wonders (2nd Ed)" → "7-wonders-2nd-ed"
    """
    import re

    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _fetch_hot_list() -> list[dict]:
    """Fetch the BGG "Hot 50" board games list.

    Returns a list of dicts with id, name, yearpublished, thumbnail.
    Gracefully returns an empty list if BGG is unreachable.
    """
    try:
        resp = requests.get(BGG_HOT_URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("bgg_fetch_failed", error=str(e))
        return []

    root = ElementTree.fromstring(resp.content)
    games = []

    for item in root.findall("item"):
        bgg_id = item.get("id", "")
        name_el = item.find("name")
        year_el = item.find("yearpublished")
        thumb_el = item.find("thumbnail")

        name = name_el.get("value", "") if name_el is not None else ""
        year = year_el.get("value", "") if year_el is not None else ""
        thumb = thumb_el.get("value", "") if thumb_el is not None else ""

        if name:
            games.append({
                "bgg_id": bgg_id,
                "name": name,
                "year": year,
                "thumbnail": thumb,
            })

    logger.info("bgg_hot_list_fetched", count=len(games))
    return games


def _fetch_ranked_list(limit: int) -> list[dict]:
    """Fetch ranked board games from BGG browse pages.

    BGG's browse list provides ~100 entries per page ordered by rank.
    We scrape only game id + display name (public metadata).
    """
    target = max(1, min(limit, _MAX_RANKED_LIMIT))
    pages = math.ceil(target / _RANKED_GAMES_PER_PAGE)

    games: list[dict] = []
    seen_ids: set[str] = set()

    for page in range(1, pages + 1):
        url = BGG_BROWSE_URL.format(page=page)
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("bgg_ranked_fetch_failed", page=page, error=str(exc))
            break

        matches = list(_BROWSE_ROW_PATTERN.finditer(resp.text))
        if not matches:
            logger.warning("bgg_ranked_parse_empty", page=page)
            break

        for match in matches:
            bgg_id = match.group("bgg_id")
            if bgg_id in seen_ids:
                continue
            seen_ids.add(bgg_id)
            games.append({
                "bgg_id": bgg_id,
                "name": html.unescape(match.group("name")).strip(),
                "rank": len(games) + 1,
            })
            if len(games) >= target:
                break

        if len(games) >= target:
            break

        # Respect BGG infra with a polite delay between page requests.
        time.sleep(_RANKED_REQUEST_DELAY)

    logger.info("bgg_ranked_list_fetched", requested=target, count=len(games))
    return games


async def sync_top_games(db: AsyncSession, publisher_id: uuid.UUID) -> int:
    """Fetch BGG Hot 50 and upsert as UPLOAD_REQUIRED catalog entries.

    Args:
        db: Active database session.
        publisher_id: UUID of the Community Catalog publisher.

    Returns:
        Number of new games created (skips existing slugs).
    """
    hot_games = _fetch_hot_list()

    if not hot_games:
        logger.warning("bgg_no_games_fetched")
        return 0

    created = 0
    for game in hot_games:
        slug = f"bgg-{_slugify(game['name'])}"

        # Check for existing entry by slug (idempotent)
        existing = await db.execute(
            select(OfficialRuleset).where(OfficialRuleset.game_slug == slug)
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug("bgg_game_exists", slug=slug)
            continue

        version = game.get("year", "2024") or "2024"

        ruleset = OfficialRuleset(
            publisher_id=publisher_id,
            game_name=game["name"],
            game_slug=slug,
            publisher_display_name="BoardGameGeek Hot",
            status="UPLOAD_REQUIRED",
            license_type="PROPRIETARY",
            is_crawlable=False,
            source_url=f"https://boardgamegeek.com/boardgame/{game['bgg_id']}",
            pinecone_namespace="",
            version=version,
        )
        db.add(ruleset)
        created += 1

    await db.flush()
    logger.info("bgg_sync_complete", created=created, total_fetched=len(hot_games))
    return created


async def sync_ranked_games(
    db: AsyncSession,
    publisher_id: uuid.UUID,
    *,
    limit: int = 1000,
) -> int:
    """Fetch BGG ranked games and upsert as metadata-only catalog entries.

    Args:
        db: Active database session.
        publisher_id: UUID of the Community Catalog publisher.
        limit: Maximum number of ranked entries to ingest (default 1000).

    Returns:
        Number of new games created (skips existing slugs).
    """
    ranked_games = _fetch_ranked_list(limit=limit)
    if not ranked_games:
        logger.warning("bgg_ranked_no_games_fetched")
        return 0

    created = 0
    for game in ranked_games:
        # Include BGG ID to keep the slug stable and collision-resistant.
        slug = f"bgg-{game['bgg_id']}-{_slugify(game['name'])}"
        existing = await db.execute(
            select(OfficialRuleset).where(OfficialRuleset.game_slug == slug)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(OfficialRuleset(
            publisher_id=publisher_id,
            game_name=game["name"],
            game_slug=slug,
            publisher_display_name="BoardGameGeek Ranked",
            status="UPLOAD_REQUIRED",
            license_type="PROPRIETARY",
            is_crawlable=False,
            source_url=f"https://boardgamegeek.com/boardgame/{game['bgg_id']}",
            pinecone_namespace="",
            version=f"BGG Rank {game['rank']}",
        ))
        created += 1

    await db.flush()
    logger.info(
        "bgg_ranked_sync_complete",
        created=created,
        total_fetched=len(ranked_games),
        limit=limit,
    )
    return created
