"""
seed_catalog.py — Populate the catalog with metadata-only entries for popular games.

LEGAL NOTE: We do NOT seed any rules text or copyrighted content.
We only seed game titles and edition info (publicly known facts).
This enables autocomplete and discovery without copyright violation.
Games are seeded with status="UPLOAD_REQUIRED" so the UI can prompt
users to upload their own legally-owned rulebook.

Usage:
    cd backend
    uv run python -m scripts.seed_catalog
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.tables import OfficialRuleset, Publisher

logger = structlog.get_logger()

# ── The "Legal" Starter Pack ─────────────────────────────────────────────────
# WHY: Top-rated BGG games that users are most likely to search for.
# We only store the name, slug, and edition — no rules content.
POPULAR_GAMES = [
    {"name": "Root", "slug": "root-board-game", "pub": "Leder Games"},
    {"name": "Wingspan", "slug": "wingspan", "pub": "Stonemaier Games"},
    {"name": "Catan (5th Ed)", "slug": "catan-5e", "pub": "Catan Studio"},
    {"name": "Ticket to Ride", "slug": "ticket-to-ride", "pub": "Days of Wonder"},
    {"name": "Twilight Imperium 4", "slug": "ti4", "pub": "Fantasy Flight Games"},
    {"name": "Gloomhaven", "slug": "gloomhaven", "pub": "Cephalofair Games"},
    {"name": "Pandemic", "slug": "pandemic", "pub": "Z-Man Games"},
    {"name": "7 Wonders", "slug": "7-wonders", "pub": "Repos Production"},
    {"name": "Azul", "slug": "azul", "pub": "Plan B Games"},
    {"name": "Spirit Island", "slug": "spirit-island", "pub": "Greater Than Games"},
    {"name": "Scythe", "slug": "scythe", "pub": "Stonemaier Games"},
    {"name": "Terraforming Mars", "slug": "terraforming-mars", "pub": "FryxGames"},
    {"name": "Dominion (2nd Ed)", "slug": "dominion-2e", "pub": "Rio Grande Games"},
    {"name": "Everdell", "slug": "everdell", "pub": "Starling Games"},
    {"name": "Ark Nova", "slug": "ark-nova", "pub": "Capstone Games"},
    {"name": "Brass: Birmingham", "slug": "brass-birmingham", "pub": "Roxley"},
    {"name": "Viticulture Essential Ed", "slug": "viticulture-ee", "pub": "Stonemaier Games"},
    {"name": "Cascadia", "slug": "cascadia", "pub": "Flatout Games"},
    {"name": "Dune: Imperium", "slug": "dune-imperium", "pub": "Dire Wolf Digital"},
    {"name": "Agricola (Revised)", "slug": "agricola-rev", "pub": "Lookout Games"},
]


async def seed() -> None:
    """Seed the database with metadata-only game entries."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        logger.info("seed_catalog_start", game_count=len(POPULAR_GAMES))

        # 1. Upsert a "Community Catalog" publisher (idempotent)
        existing = await db.execute(
            select(Publisher).where(Publisher.slug == "community")
        )
        community_pub = existing.scalar_one_or_none()

        if community_pub is None:
            community_pub = Publisher(
                id=uuid.uuid4(),
                name="Community Catalog",
                slug="community",
                contact_email="support@arbiter-ai.com",
                api_key_hash="seeder_placeholder",
                verified=True,
            )
            db.add(community_pub)
            await db.flush()
            logger.info("seed_publisher_created", publisher_id=str(community_pub.id))
        else:
            logger.info("seed_publisher_exists", publisher_id=str(community_pub.id))

        # 2. Seed games (skip duplicates by slug)
        seeded = 0
        for game in POPULAR_GAMES:
            existing_game = await db.execute(
                select(OfficialRuleset).where(
                    OfficialRuleset.game_slug == game["slug"]
                )
            )
            if existing_game.scalar_one_or_none() is not None:
                logger.debug("seed_game_exists", slug=game["slug"])
                continue

            ruleset = OfficialRuleset(
                publisher_id=community_pub.id,
                game_name=game["name"],
                game_slug=game["slug"],
                # WHY: "UPLOAD_REQUIRED" signals the frontend to prompt users
                # to upload their own rulebook before they can play.
                status="UPLOAD_REQUIRED",
                pinecone_namespace=f"placeholder_{game['slug']}",
                version="1.0",
            )
            db.add(ruleset)
            seeded += 1

        await db.commit()
        logger.info("seed_catalog_complete", seeded=seeded, skipped=len(POPULAR_GAMES) - seeded)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
