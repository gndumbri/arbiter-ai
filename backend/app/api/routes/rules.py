"""Rules upload routes — PDF ingestion endpoints."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Form, HTTPException, UploadFile
from sqlalchemy import select, update

from app.api.deps import DbSession, GetSettings
from app.models.schemas import ErrorResponse
from app.models.tables import RulesetMetadata
from app.workers.tasks import ingest_ruleset

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
    game_name: str = Form("Unknown Game"),
    source_type: str = Form("BASE"),
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

    # Dispatch async ingestion task
    try:
        # Pass file path as string. In production with multiple workers/nodes,
        # this path must be on a shared volume (EFS/NFS) or S3-backed.
        # For this Docker Compose setup, we'll assume a shared volume.
        ingest_ruleset.delay(
            file_path=str(tmp_path),
            ruleset_id=str(ruleset_id),
            user_id="anonymous",  # TODO: get from auth
            session_id=str(session_id),
            game_name=game_name,
            source_type=source_type,
            source_priority=source_priority,
        )

        logger.info("ruleset_ingestion_queued", ruleset_id=str(ruleset_id))

        return {
            "ruleset_id": str(ruleset_id),
            "status": "PROCESSING",
            "chunk_count": 0,
            "message": "Ruleset processing started. Check status endpoint for updates.",
        }

    except Exception as exc:
        # Cleanup if dispatch fails
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await db.execute(
            update(RulesetMetadata)
            .where(RulesetMetadata.id == ruleset_id)
            .values(status="FAILED", error_message="Task dispatch failed")
        )
        logger.exception("Task dispatch failed", ruleset_id=str(ruleset_id))
        raise HTTPException(status_code=500, detail="Failed to queue processing task") from exc

    # Note: We do NOT clean up tmp_dir here eagerly, because the worker needs it.
    # The worker is responsible for cleanup after processing.


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


@router.get("/rulesets")
async def list_rulesets(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    """List all uploaded rulesets."""
    result = await db.execute(
        select(RulesetMetadata)
        .order_by(RulesetMetadata.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    rulesets = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "game_name": r.game_name,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "chunk_count": r.chunk_count,
            "filename": r.filename,
            "session_id": str(r.session_id),
            "source_type": r.source_type,
        }
        for r in rulesets
    ]
