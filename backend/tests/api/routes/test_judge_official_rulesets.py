"""Regression tests for judge official-ruleset namespace resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
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
    """Override auth dependency with a deterministic test user."""

    def _mock_user():
        return mock_user

    app.dependency_overrides[get_current_user] = _mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_judge_uses_session_active_official_rulesets(
    client,
    db_session,
    override_user,
    monkeypatch,
):
    """Judge should query official namespaces when no uploaded rulesets exist."""
    official_ruleset_id = uuid.uuid4()
    captured: dict[str, list[str]] = {}

    # 1) Session lookup
    mock_session = MagicMock(spec=Session)
    mock_session.expires_at = datetime.now(UTC) + timedelta(hours=24)
    mock_session.game_name = "Dungeons & Dragons 5th Edition"
    mock_session.persona = None
    mock_session.system_prompt_override = None
    mock_session.active_ruleset_ids = [official_ruleset_id]
    res_session = MagicMock()
    res_session.scalar_one_or_none.return_value = mock_session

    # 2) Uploaded session rulesets lookup -> none
    res_uploaded = MagicMock()
    res_uploaded.all.return_value = []

    # 3) Official active rulesets lookup -> returns the attached ready ruleset
    res_official = MagicMock()
    res_official.all.return_value = [(official_ruleset_id,)]

    # 4) Subscription lookup -> none (FREE fallback)
    res_sub = MagicMock()
    res_sub.scalar_one_or_none.return_value = None

    # 5) Tier config lookup -> missing (uses default daily limit)
    res_tier = MagicMock()
    res_tier.scalar_one_or_none.return_value = None

    # 6) Usage count lookup -> under limit
    res_usage = MagicMock()
    res_usage.scalar_one.return_value = 0

    db_session.execute.side_effect = [
        res_session,
        res_uploaded,
        res_official,
        res_sub,
        res_tier,
        res_usage,
    ]

    class DummyRegistry:
        def get_llm(self):
            return object()

        def get_embedder(self):
            return object()

        def get_vector_store(self):
            return object()

        def get_reranker(self):
            return object()

    class DummyEngine:
        def __init__(self, **kwargs):  # noqa: ARG002
            pass

        async def adjudicate(  # noqa: PLR0913
            self,
            *,
            query: str,
            namespaces: list[str],
            game_name: str | None,
            persona: str | None,
            system_prompt_override: str | None,
            conversation_history: list[dict[str, str]],
        ):
            captured["namespaces"] = namespaces
            return SimpleNamespace(
                query_id=str(uuid.uuid4()),
                verdict=f"Resolved: {query}",
                confidence=0.92,
                reasoning_chain=None,
                citations=[
                    SimpleNamespace(
                        source=game_name or "Unknown",
                        page=None,
                        section=None,
                        snippet="Rules text snippet",
                        is_official=True,
                    )
                ],
                conflicts=None,
                follow_up_hint=None,
                model="mock-model",
                expanded_query=query,
                latency_ms=12,
            )

    monkeypatch.setattr("app.api.routes.judge.get_provider_registry", lambda: DummyRegistry())
    monkeypatch.setattr("app.api.routes.judge.AdjudicationEngine", DummyEngine)

    response = client.post(
        "/api/v1/judge",
        json={
            "query": "How does advantage work?",
            "game_name": "Dungeons & Dragons 5th Edition",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    )

    assert response.status_code == 200
    assert captured["namespaces"] == [str(official_ruleset_id)]
