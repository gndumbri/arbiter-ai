from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.deps import get_current_user
from app.main import app
from app.models.tables import Subscription, SubscriptionTier

# Mock User
mock_user = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "test@example.com",
    "tier": "FREE"
}

@pytest.fixture
def override_user():
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

def test_judge_billing_limit_reached(client, db_session, override_user):
    """Test that FREE tier user gets 429 when limit is reached."""
    
    # Mock sequence of db.execute calls
    # 1. Subscription query -> Return FREE subscription
    # 2. Tier config query -> Return FREE tier with limit 5
    # 3. Usage count query -> Return 5 (Limit Reached)
    
    mock_subscription = MagicMock(spec=Subscription)
    mock_subscription.plan_tier = "FREE"
    
    mock_tier = MagicMock(spec=SubscriptionTier)
    mock_tier.daily_query_limit = 5
    
    # We need to construct the AsyncMock side_effect carefully
    # logic in judge.py:
    # result = await db.execute(stmt) -> subscription
    # tier_result = await db.execute(tier_stmt) -> tier_config
    # usage_result = await db.execute(usage_stmt) -> usage_count
    
    # Mock Result objects
    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = mock_subscription
    
    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = mock_tier
    
    res3 = MagicMock()
    res3.scalar_one.return_value = 5  # Limit reached
    
    db_session.execute.side_effect = [res1, res2, res3]
    
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
    
    # 1. Subscription -> PRO
    # 2. Tier Config -> Limit -1
    # 3. No usage check query needed! (Logic skips if limit == -1)
    
    mock_subscription = MagicMock(spec=Subscription)
    mock_subscription.plan_tier = "PRO"
    
    mock_tier = MagicMock(spec=SubscriptionTier)
    mock_tier.daily_query_limit = -1
    
    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = mock_subscription
    
    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = mock_tier
    
    # Only 2 executes expected
    db_session.execute.side_effect = [res1, res2]

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
    assert response.status_code == 500 # Adjudication failed
