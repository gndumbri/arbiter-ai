"""Celery application factory."""

from __future__ import annotations

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    settings = get_settings()

    app = Celery(
        "arbiter",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )

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
    )

    return app


celery_app = create_celery_app()
