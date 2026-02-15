"""One-shot sync for open-license rules ingestion.

Usage:
    cd backend
    uv run python -m scripts.sync_open_rules
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.tables import Publisher
from app.services.catalog.open5e_ingester import sync_open_licensed_documents

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
            stats = await sync_open_licensed_documents(
                db,
                publisher.id,
                max_documents=settings.open_rules_max_documents,
                allowed_license_keywords=settings.open_rules_allowed_licenses_list,
                force_reindex=settings.open_rules_force_reindex,
            )
            logger.info("sync_open_rules_done", **stats)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())

