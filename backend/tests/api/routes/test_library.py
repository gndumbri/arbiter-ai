"""Tests for library route behavior."""

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


def test_start_session_from_library_reuses_indexed_session(client, db_session, override_user):
    """POST /library/{id}/sessions should reuse existing indexed session."""
    now = datetime.now(UTC)
    entry_id = uuid.uuid4()

    mock_entry = MagicMock()
    mock_entry.id = entry_id
    mock_entry.user_id = uuid.UUID(mock_user["id"])
    mock_entry.game_name = "Root"
    mock_entry.official_ruleset_ids = None
    mock_entry.personal_ruleset_ids = None
    mock_entry.last_queried = None

    mock_session = MagicMock(spec=Session)
    mock_session.id = uuid.uuid4()
    mock_session.user_id = uuid.UUID(mock_user["id"])
    mock_session.game_name = "Root"
    mock_session.persona = None
    mock_session.system_prompt_override = None
    mock_session.active_ruleset_ids = None
    mock_session.created_at = now
    mock_session.expires_at = now + timedelta(hours=24)

    res_entry = MagicMock()
    res_entry.scalar_one_or_none.return_value = mock_entry
    res_indexed = MagicMock()
    res_indexed.scalar_one_or_none.return_value = mock_session

    db_session.execute.side_effect = [res_entry, res_indexed]

    response = client.post(f"/api/v1/library/{entry_id}/sessions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(mock_session.id)
    assert payload["game_name"] == "Root"


def test_start_session_from_library_409_when_no_rules(client, db_session, override_user):
    """POST /library/{id}/sessions should return 409 when no rules are linked."""
    entry_id = uuid.uuid4()

    mock_entry = MagicMock()
    mock_entry.id = entry_id
    mock_entry.user_id = uuid.UUID(mock_user["id"])
    mock_entry.game_name = "Custom Homebrew"
    mock_entry.official_ruleset_ids = None
    mock_entry.personal_ruleset_ids = None
    mock_entry.last_queried = None

    res_entry = MagicMock()
    res_entry.scalar_one_or_none.return_value = mock_entry
    res_indexed = MagicMock()
    res_indexed.scalar_one_or_none.return_value = None

    db_session.execute.side_effect = [res_entry, res_indexed]

    response = client.post(f"/api/v1/library/{entry_id}/sessions")
    assert response.status_code == 409
    assert "No ready rules are linked" in response.json()["detail"]
