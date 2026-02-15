"""Celery tasks for async background processing."""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from uuid import UUID

from celery import shared_task
from sqlalchemy import update

from app.core.ingestion import IngestionPipeline
from app.core.registry import get_provider_registry
from app.models.database import get_async_session
from app.models.tables import RulesetMetadata

logger = logging.getLogger(__name__)


async def _run_ingest(
    file_path: str,
    ruleset_id: str,
    user_id: str,
    session_id: str,
    game_name: str,
    source_type: str,
    source_priority: int,
) -> dict:
    """Async helper to run the ingestion pipeline.

    Done this way because Celery tasks are synchronous wrappers
    around async code in this context.
    """
    registry = get_provider_registry()
    pipeline = IngestionPipeline(
        llm=registry.get_llm(),
        embedder=registry.get_embedder(),
        vector_store=registry.get_vector_store(),
        parser=registry.get_parser(),
    )

    try:
        result = await pipeline.process(
            file_path=file_path,
            ruleset_id=ruleset_id,
            user_id=user_id,
            session_id=session_id,
            game_name=game_name,
            source_type=source_type,
            source_priority=source_priority,
        )

        # Update DB status to INDEXED
        async for db in get_async_session():
            await db.execute(
                update(RulesetMetadata)
                .where(RulesetMetadata.id == UUID(ruleset_id))
                .values(
                    status="INDEXED",
                    chunk_count=result.chunk_count,
                    file_hash=result.file_hash,
                )
            )
            await db.commit()

        logger.info("IngestionTask success ruleset_id=%s", ruleset_id)
        return {
            "status": "INDEXED",
            "chunk_count": result.chunk_count,
            "ruleset_id": ruleset_id,
        }

    except Exception as exc:
        logger.exception("IngestionTask failed ruleset_id=%s", ruleset_id)
        # Update DB status to FAILED
        async for db in get_async_session():
            await db.execute(
                update(RulesetMetadata)
                .where(RulesetMetadata.id == UUID(ruleset_id))
                .values(
                    status="FAILED",
                    error_message=str(exc),
                )
            )
            await db.commit()
        raise
    finally:
        # Remove now-empty per-ruleset upload directory.
        shutil.rmtree(Path(file_path).parent, ignore_errors=True)


@shared_task(bind=True, max_retries=3)
def ingest_ruleset(
    self,
    file_path: str,
    ruleset_id: str,
    user_id: str,
    session_id: str,
    game_name: str,
    source_type: str,
    source_priority: int,
) -> dict:
    """Wrap async ingestion logic in a synchronous Celery task."""
    try:
        # Run the async function in a new event loop
        return asyncio.run(
            _run_ingest(
                file_path=file_path,
                ruleset_id=ruleset_id,
                user_id=user_id,
                session_id=session_id,
                game_name=game_name,
                source_type=source_type,
                source_priority=source_priority,
            )
        )
    except Exception as exc:
        # Retry only on specific transient errors if needed
        # For now, just fail hard to avoid infinite loops on bad PDFs
        # raise self.retry(exc=exc, countdown=60) if False else exc
        raise exc from exc
