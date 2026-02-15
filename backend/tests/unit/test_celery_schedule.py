"""Tests for Celery Beat schedule wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.workers.celery_app import create_celery_app


@patch("app.workers.celery_app.get_settings")
def test_create_celery_app_includes_periodic_sync_tasks(mock_get_settings) -> None:
    mock_get_settings.return_value = SimpleNamespace(
        redis_url="redis://localhost:6379/0",
        catalog_sync_enabled=True,
        catalog_sync_cron="0 */6 * * *",
        open_rules_sync_enabled=True,
        open_rules_sync_cron="30 4 * * *",
    )

    app = create_celery_app()
    beat_schedule = app.conf.beat_schedule

    assert "catalog-metadata-sync" in beat_schedule
    assert beat_schedule["catalog-metadata-sync"]["task"] == "app.workers.tasks.sync_catalog_metadata"
    assert "open-license-rules-sync" in beat_schedule
    assert beat_schedule["open-license-rules-sync"]["task"] == "app.workers.tasks.sync_open_license_rules"


@patch("app.workers.celery_app.get_settings")
def test_create_celery_app_omits_sync_tasks_when_disabled(mock_get_settings) -> None:
    mock_get_settings.return_value = SimpleNamespace(
        redis_url="redis://localhost:6379/0",
        catalog_sync_enabled=False,
        catalog_sync_cron="0 */6 * * *",
        open_rules_sync_enabled=False,
        open_rules_sync_cron="30 4 * * *",
    )

    app = create_celery_app()

    assert app.conf.beat_schedule == {}

