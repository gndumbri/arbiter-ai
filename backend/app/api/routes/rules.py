"""Rules upload routes — PDF ingestion endpoints."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select, update

from app.api.deps import DbSession, GetSettings
from app.core.ingestion import IngestionError, IngestionPipeline
from app.core.registry import get_provider_registry
from app.models.schemas import ErrorResponse
from app.models.tables import RulesetMetadata

router = APIRouter(prefix="/api/v1", tags=["rules"])
logger = structlog.get_logger()


@router.post(
    "/sessions/{session_id}/rulesets",
    status_code=202,
    responses={
        422: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
    },
)
async def upload_ruleset(
    session_id: uuid.UUID,
    file: UploadFile,
    db: DbSession,
    settings: GetSettings,
    game_name: str = "Unknown Game",
    source_type: str = "BASE",
) -> dict:
    """Upload a PDF ruleset for ingestion.

    The file is validated, classified, parsed, chunked, embedded,
    and indexed asynchronously. Returns a tracking ID immediately.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=422,
            detail="Only PDF files are accepted",
        )

    # Create ruleset_metadata entry
    ruleset_id = uuid.uuid4()
    source_priority = {"BASE": 0, "EXPANSION": 10, "ERRATA": 100}.get(
        source_type, 0
    )

    ruleset = RulesetMetadata(
        id=ruleset_id,
        session_id=session_id,
        filename=file.filename,
        game_name=game_name,
        file_hash="pending",
        source_type=source_type,
        source_priority=source_priority,
        status="PROCESSING",
    )
    db.add(ruleset)
    await db.flush()

    # Save upload to temp directory
    tmp_dir = Path(tempfile.mkdtemp(prefix="arbiter_"))
    tmp_path = tmp_dir / file.filename
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # For now, process synchronously. TODO: dispatch to Celery worker
    # In production, this would be: ingest_task.delay(str(tmp_path), ...)
    try:
        registry = get_provider_registry()
        pipeline = IngestionPipeline(
            llm=registry.get_llm(),
            embedder=registry.get_embedder(),
            vector_store=registry.get_vector_store(),
            parser=registry.get_parser(),
        )

        # TODO: get user_id from auth context
        user_id = "anonymous"

        result = await pipeline.process(
            file_path=str(tmp_path),
            ruleset_id=str(ruleset_id),
            user_id=user_id,
            session_id=str(session_id),
            game_name=game_name,
            source_type=source_type,
            source_priority=source_priority,
        )

        # Update metadata
        await db.execute(
            update(RulesetMetadata)
            .where(RulesetMetadata.id == ruleset_id)
            .values(
                status="INDEXED",
                chunk_count=result.chunk_count,
                pinecone_namespace=result.namespace,
            )
        )

        logger.info(
            "ruleset_indexed",
            ruleset_id=str(ruleset_id),
            chunks=result.chunk_count,
        )

        return {
            "ruleset_id": str(ruleset_id),
            "status": "INDEXED",
            "chunk_count": result.chunk_count,
            "message": "Ruleset processed and indexed successfully",
        }

    except IngestionError as exc:
        await db.execute(
            update(RulesetMetadata)
            .where(RulesetMetadata.id == ruleset_id)
            .values(status="FAILED")
        )
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except Exception as exc:
        await db.execute(
            update(RulesetMetadata)
            .where(RulesetMetadata.id == ruleset_id)
            .values(status="FAILED")
        )
        logger.exception("Ingestion failed", ruleset_id=str(ruleset_id))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        # Cleanup temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/rulesets/{ruleset_id}/status")
async def get_ruleset_status(
    ruleset_id: uuid.UUID,
    db: DbSession,
) -> dict:
    """Get the processing status of a ruleset."""
    result = await db.execute(
        select(RulesetMetadata).where(RulesetMetadata.id == ruleset_id)
    )
    ruleset = result.scalar_one_or_none()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    return {
        "ruleset_id": str(ruleset.id),
        "status": ruleset.status,
        "game_name": ruleset.game_name,
        "source_type": ruleset.source_type,
        "chunk_count": ruleset.chunk_count,
        "created_at": ruleset.created_at.isoformat() if ruleset.created_at else None,
    }
