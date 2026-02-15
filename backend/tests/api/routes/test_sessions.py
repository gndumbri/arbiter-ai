"""Tests for sessions route behavior."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_current_user
from app.main import app
from app.models.tables import Session

mock_user = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "test@example.com",
    "tier": "FREE",
}


@pytest.fixture
def override_user():
    """Override auth dependency for route tests."""

    def _mock_user():
        return mock_user

    app.dependency_overrides[get_current_user] = _mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_get_session_returns_owned_session(client, db_session, override_user):
    """GET /sessions/{id} should return a single owned session."""
    now = datetime.now(UTC)
    session_id = uuid.uuid4()
    user_id = uuid.UUID(mock_user["id"])

    mock_session = MagicMock(spec=Session)
    mock_session.id = session_id
    mock_session.user_id = user_id
    mock_session.game_name = "Root"
    mock_session.persona = "Guide NPC"
    mock_session.system_prompt_override = None
    mock_session.active_ruleset_ids = None
    mock_session.created_at = now
    mock_session.expires_at = now + timedelta(hours=1)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session
    db_session.execute.return_value = mock_result

    response = client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(session_id)
    assert payload["game_name"] == "Root"
    assert payload["persona"] == "Guide NPC"


def test_get_session_404_when_missing(client, db_session, override_user):
    """GET /sessions/{id} should return 404 when not found."""
    session_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute.return_value = mock_result

    response = client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found."

