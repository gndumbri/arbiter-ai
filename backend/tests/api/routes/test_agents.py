"""Tests for agents route behavior."""

from __future__ import annotations

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


def test_list_agents_returns_session_payload(client, db_session, override_user):
    """GET /agents should return sessions with persona metadata."""
    now = datetime.now(UTC)
    mock_session = MagicMock(spec=Session)
    mock_session.id = "123e4567-e89b-12d3-a456-426614174999"
    mock_session.game_name = "Root"
    mock_session.persona = "Helpful Guide"
    mock_session.system_prompt_override = None
    mock_session.created_at = now
    mock_session.expires_at = now + timedelta(hours=1)
    mock_session.active_ruleset_ids = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_session]
    db_session.execute.return_value = mock_result

    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["game_name"] == "Root"
    assert payload[0]["persona"] == "Helpful Guide"
    assert payload[0]["active"] is True
