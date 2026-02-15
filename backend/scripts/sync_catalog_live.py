"""One-shot sync for live catalog metadata sources.

Usage:
    cd backend
    uv run python -m scripts.sync_catalog_live
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.tables import Publisher
from app.services.catalog.bgg_fetcher import sync_ranked_games, sync_top_games

logger = structlog.get_logger()


async def _ensure_community_publisher(db) -> Publisher:
    existing = await db.execute(select(Publisher).where(Publisher.slug == "community"))
    publisher = existing.scalar_one_or_none()
    if publisher is not None:
        return publisher

    publisher = Publisher(
        id=uuid.uuid4(),
        name="Community Catalog",
        slug="community",
        contact_email="support@arbiter-ai.com",
        api_key_hash="manual_sync_placeholder",
        verified=True,
    )
    db.add(publisher)
    await db.flush()
    return publisher


async def run() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            publisher = await _ensure_community_publisher(db)
            hot_created = await sync_top_games(db, publisher.id)
            ranked_created = await sync_ranked_games(
                db,
                publisher.id,
                limit=settings.catalog_ranked_game_limit,
            )
            await db.commit()
            logger.info(
                "sync_catalog_live_done",
                hot_created=hot_created,
                ranked_created=ranked_created,
                ranked_limit=settings.catalog_ranked_game_limit,
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())

