"""Rules upload routes — PDF ingestion endpoints."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Form, HTTPException, UploadFile
from sqlalchemy import func, select, update

from app.api.abuse_detection import AbuseDetector
from app.api.deps import CurrentUser, DbSession, GetSettings, RedisDep
from app.api.rate_limit import RateLimitDep
from app.models.schemas import ErrorResponse
from app.models.tables import RulesetMetadata, Session
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
    user: CurrentUser,
    db: DbSession,
    settings: GetSettings,
    limiter: RateLimitDep,
    redis: RedisDep,
    game_name: str = Form("Unknown Game"),
    source_type: str = Form("BASE"),
) -> dict:
    """Upload a PDF ruleset for ingestion.

    The file is validated, classified, parsed, chunked, embedded,
    and indexed asynchronously. Returns a tracking ID immediately.
    """
    # ── Input validation ──────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=422,
            detail="Only PDF files are accepted",
        )

    # ── Rate limiting + abuse detection ───────────────────────────────────
    # WHY: Uploads are expensive (storage + embedding pipeline). Limit daily
    # count per tier and detect rapid-fire upload abuse patterns.
    await limiter.check_and_increment(
        user_id=str(user["id"]),
        tier=user["tier"],
        category="upload",
    )

    # Detect upload velocity abuse (>5 in 5 minutes = bot behavior)
    detector = AbuseDetector(redis)
    await detector.check_upload_velocity(str(user["id"]))

    # ── Per-user active ruleset cap ───────────────────────────────────────
    # WHY: Prevent storage abuse. FREE users: 10 active rulesets max.
    max_active = 50 if user["tier"] in ("PRO", "ADMIN") else 10
    count_result = await db.execute(
        select(func.count(RulesetMetadata.id)).where(
            RulesetMetadata.user_id == user["id"],
            RulesetMetadata.status.notin_(["FAILED", "DELETED"]),
        )
    )
    active_count = count_result.scalar_one() or 0
    if active_count >= max_active:
        raise HTTPException(
            status_code=429,
            detail=f"You've reached the max number of rulesets ({max_active}). "
            "Delete some old ones or upgrade your plan!",
        )

    # WHY: Validate source_type to prevent arbitrary values being stored.
    allowed_source_types = {"BASE", "EXPANSION", "ERRATA"}
    if source_type not in allowed_source_types:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of: {', '.join(sorted(allowed_source_types))}",
        )

    # Enforce session ownership before accepting upload bytes.
    session_result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user["id"],
        )
    )
    session_row = session_result.scalar_one_or_none()
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    # WHY: Sanitize the filename to prevent path traversal attacks.
    # A malicious filename like "../../etc/passwd" would write outside
    # the temp directory. We strip path separators and non-safe characters.
    safe_name = re.sub(r"[^\w.\-]", "_", Path(file.filename).name)
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    # Create ruleset_metadata entry
    ruleset_id = uuid.uuid4()
    source_priority = {"BASE": 0, "EXPANSION": 10, "ERRATA": 100}.get(
        source_type, 0
    )

    ruleset = RulesetMetadata(
        id=ruleset_id,
        session_id=session_id,
        user_id=user["id"],
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
    # WHY: Celery workers need to read the uploaded file; use a configured
    # shared mount path rather than Python's random temp dir.
    tmp_dir = Path(settings.uploads_dir) / str(ruleset_id)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / safe_name
    max_bytes = 20 * 1024 * 1024  # 20MB upload cap
    try:
        # WHY: Read in chunks with a hard cap to prevent DoS via huge uploads.
        # The ingestion pipeline also checks size, but catching it here avoids
        # writing a multi-GB file to disk first.
        bytes_written = 0
        with open(tmp_path, "wb") as f:
            while chunk := await file.read(8192):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    f.close()
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"That rulebook is too hefty! Max upload size is {max_bytes // (1024 * 1024)}MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("File save failed for session %s", session_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail="Oops — the Arbiter dropped your rulebook. Please try uploading again!",
        ) from exc

    # Dispatch async ingestion task
    try:
        # Pass file path as string. In production with multiple workers/nodes,
        # this path must be on a shared volume (EFS/NFS) or S3-backed.
        # For this Docker Compose setup, we'll assume a shared volume.
        ingest_ruleset.delay(
            file_path=str(tmp_path),
            ruleset_id=str(ruleset_id),
            user_id=str(user["id"]),
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
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get the processing status of a ruleset."""
    result = await db.execute(
        select(RulesetMetadata).where(
            RulesetMetadata.id == ruleset_id,
            RulesetMetadata.user_id == user["id"],
        )
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
    user: CurrentUser,
    db: DbSession,
    session_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    """List the current user's uploaded rulesets."""
    stmt = select(RulesetMetadata).where(RulesetMetadata.user_id == user["id"])
    if session_id:
        stmt = stmt.where(RulesetMetadata.session_id == session_id)

    result = await db.execute(
        stmt
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
