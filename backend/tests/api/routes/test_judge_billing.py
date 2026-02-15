"""Tests for judge billing/rate-limiting.

Verifies that FREE-tier users hit a 429 when their daily query
limit is reached, and PRO-tier users are not blocked.

WHY these tests exist: The judge.py route implements tier-based
rate limiting. These tests ensure the billing/rate-limit checks
work correctly without needing a real database or Stripe.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_current_user
from app.main import app
from app.models.tables import Session, Subscription, SubscriptionTier

# Mock User
mock_user = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "test@example.com",
    "tier": "FREE"
}

@pytest.fixture
def override_user():
    """Override auth dep with a mock FREE-tier user."""
    def _mock_user():
        return mock_user
    app.dependency_overrides[get_current_user] = _mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

def test_judge_billing_limit_reached(client, db_session, override_user):
    """Test that FREE tier user gets 429 when limit is reached."""

    # Mock sequence of db.execute calls in judge.py:
    # 1. Session query -> Return valid non-expired session
    # 2. Namespace resolution query -> Return indexed ruleset namespace
    # 3. Subscription query -> Return FREE subscription
    # 4. Tier config query -> Return FREE tier with limit 5
    # 5. Usage count query -> Return 5 (Limit Reached)

    # Result 1: Session exists and is not expired
    mock_session = MagicMock(spec=Session)
    mock_session.expires_at = datetime.now(UTC) + timedelta(hours=12)
    res_session = MagicMock()
    res_session.scalar_one_or_none.return_value = mock_session

    # Result 2: Namespace resolution
    res_namespaces = MagicMock()
    res_namespaces.all.return_value = [
        ("223e4567-e89b-12d3-a456-426614174001",),
    ]

    # Result 3: Subscription query
    mock_subscription = MagicMock(spec=Subscription)
    mock_subscription.plan_tier = "FREE"
    res_sub = MagicMock()
    res_sub.scalar_one_or_none.return_value = mock_subscription

    # Result 4: Tier config query
    mock_tier = MagicMock(spec=SubscriptionTier)
    mock_tier.daily_query_limit = 5
    res_tier = MagicMock()
    res_tier.scalar_one_or_none.return_value = mock_tier

    # Result 5: Usage count query
    res_usage = MagicMock()
    res_usage.scalar_one.return_value = 5  # Limit reached

    db_session.execute.side_effect = [res_session, res_namespaces, res_sub, res_tier, res_usage]

    response = client.post(
        "/api/v1/judge",
        json={
            "query": "Can a cleric use a shield?",
            "game_name": "D&D 5e",
            "session_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    )

    assert response.status_code == 429
    assert "Daily query limit reached" in response.json()["detail"]

def test_judge_billing_pro_unlimited(client, db_session, override_user):
    """Test that PRO tier user (unlimited) does not get blocked."""

    # 1. Session query -> valid session
    # 2. Namespace resolution -> indexed ruleset exists
    # 3. Subscription -> PRO
    # 4. Tier Config -> Limit -1 (unlimited)
    # No usage check! (Logic skips if limit == -1)

    mock_session = MagicMock(spec=Session)
    mock_session.expires_at = datetime.now(UTC) + timedelta(days=30)
    res_session = MagicMock()
    res_session.scalar_one_or_none.return_value = mock_session

    res_namespaces = MagicMock()
    res_namespaces.all.return_value = [
        ("223e4567-e89b-12d3-a456-426614174001",),
    ]

    mock_subscription = MagicMock(spec=Subscription)
    mock_subscription.plan_tier = "PRO"
    res_sub = MagicMock()
    res_sub.scalar_one_or_none.return_value = mock_subscription

    mock_tier = MagicMock(spec=SubscriptionTier)
    mock_tier.daily_query_limit = -1
    res_tier = MagicMock()
    res_tier.scalar_one_or_none.return_value = mock_tier

    db_session.execute.side_effect = [res_session, res_namespaces, res_sub, res_tier]

    # Mock Engine (since we pass billing check, it tries to run engine)
    # It will fail with 500 due to missing Pinecone/LLM keys, which is EXPECTED.
    # We just want to ensure it didn't return 429.

    response = client.post(
        "/api/v1/judge",
        json={
            "query": "foo",
            "game_name": "bar",
            "session_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    )

    assert response.status_code != 429
    assert response.status_code == 500  # Adjudication failed (no LLM keys)
