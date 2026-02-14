"""Health check endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSession, RedisDep
from app.models.schemas import HealthResponse

logger = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: DBSession, redis: RedisDep) -> HealthResponse:
    """Service health check with database and Redis connectivity."""
    db_status = "connected"
    redis_status = "connected"

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        db_status = "disconnected"

    try:
        await redis.ping()
    except Exception as exc:
        logger.error("health_check_redis_failed", error=str(exc))
        redis_status = "disconnected"

    is_healthy = db_status == "connected" and redis_status == "connected"
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        database=db_status,
        redis=redis_status,
    )
