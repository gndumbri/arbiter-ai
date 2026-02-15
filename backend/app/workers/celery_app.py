"""Celery application factory."""

from __future__ import annotations

import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

logger = logging.getLogger(__name__)


def _parse_cron(expr: str) -> crontab:
    """Parse a 5-field cron expression into Celery crontab."""
    parts = expr.split()
    if len(parts) != 5:
        logger.warning("Invalid cron expression '%s'. Falling back to '0 4 * * *'.", expr)
        parts = ["0", "4", "*", "*", "*"]
    return crontab(
        minute=parts[0],
        hour=parts[1],
        day_of_month=parts[2],
        month_of_year=parts[3],
        day_of_week=parts[4],
    )


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    settings = get_settings()

    app = Celery(
        "arbiter",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )

    beat_schedule: dict[str, dict] = {}
    if settings.catalog_sync_enabled:
        beat_schedule["catalog-metadata-sync"] = {
            "task": "app.workers.tasks.sync_catalog_metadata",
            "schedule": _parse_cron(settings.catalog_sync_cron),
        }
    if settings.open_rules_sync_enabled:
        beat_schedule["open-license-rules-sync"] = {
            "task": "app.workers.tasks.sync_open_license_rules",
            "schedule": _parse_cron(settings.open_rules_sync_cron),
        }

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        # Optimize for short tasks if needed, but ingestion is long-running
        # so default prefetch is fine.
        broker_connection_retry_on_startup=True,
        beat_schedule=beat_schedule,
    )

    return app


celery_app = create_celery_app()
