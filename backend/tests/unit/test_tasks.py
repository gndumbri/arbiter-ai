"""Tests for Celery task dispatch."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.workers.tasks import ingest_ruleset


def test_upload_ruleset_dispatches_task(
    client: TestClient, db_session: MagicMock
) -> None:
    """Upload endpoint should dispatch Celery task and return 202."""
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Mock auth + session ownership lookup.
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "email": "test@example.com",
        "tier": "FREE",
        "role": "USER",
    }
    mock_session = MagicMock()
    res_count = MagicMock()
    res_count.scalar_one.return_value = 0
    res_session = MagicMock()
    res_session.scalar_one_or_none.return_value = mock_session
    db_session.execute.side_effect = [res_count, res_session]

    # Mock the entire Celery task object in the module
    try:
        with patch("app.api.routes.rules.ingest_ruleset") as mock_task:
            response = client.post(
                f"/api/v1/sessions/{session_id}/rulesets",
                files={"file": ("rules.pdf", b"%PDF-1.4...", "application/pdf")},
                data={"game_name": "Test Game", "source_type": "BASE"},
            )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "PROCESSING"
            assert "ruleset_id" in data

            # Verify task delay was called
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args[1]
            assert call_args["game_name"] == "Test Game"
            assert call_args["source_type"] == "BASE"
            assert str(session_id) == call_args["session_id"]
            assert call_args["user_id"] == str(user_id)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@patch("app.workers.tasks.IngestionPipeline")
@patch("app.workers.tasks.get_provider_registry")
@patch("app.workers.tasks.get_async_session")
def test_ingest_ruleset_task(
    mock_get_session: MagicMock,
    mock_registry: MagicMock,
    mock_pipeline_cls: MagicMock,
) -> None:
    """Task should initialize pipeline and call process."""
    # Setup mocks
    mock_pipeline = mock_pipeline_cls.return_value
    # process is async, so it must be an AsyncMock or return a coroutine
    mock_pipeline.process = AsyncMock(
        return_value=MagicMock(chunk_count=10, namespace="ns", file_hash="hash")
    )

    # Mock get_async_session to return an async iterator
    mock_db = AsyncMock()
    mock_get_session.return_value.__aiter__.return_value = [mock_db]

    # Run task
    ingest_ruleset(
        file_path="/tmp/test.pdf",
        ruleset_id=str(uuid.uuid4()),
        user_id="user1",
        session_id=str(uuid.uuid4()),
        game_name="Game",
        source_type="BASE",
        source_priority=0,
    )

    # Verify pipeline called
    mock_pipeline_cls.assert_called_once()
    mock_pipeline.process.assert_called_once()
