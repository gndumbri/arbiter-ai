"""Unit tests for rate limiter resilience behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.api.rate_limit import RateLimiter
from app.config import Settings


@pytest.mark.anyio
async def test_rate_limiter_allows_when_redis_unavailable() -> None:
    """Limiter should fail-open when Redis is unavailable."""
    redis = AsyncMock()
    redis.incr.side_effect = RedisError("redis unavailable")

    limiter = RateLimiter(redis=redis, settings=Settings())
    result = await limiter.check_and_increment(
        user_id="user-1",
        tier="FREE",
        category="session",
    )

    assert result["allowed"] is True
    assert result["category"] == "session"
    assert result.get("degraded") is True


@pytest.mark.anyio
async def test_rate_limiter_unlimited_tier_bypasses_redis() -> None:
    """Unlimited tiers should bypass Redis calls entirely."""
    redis = AsyncMock()

    limiter = RateLimiter(redis=redis, settings=Settings())
    result = await limiter.check_and_increment(
        user_id="user-1",
        tier="PRO",
        category="query",
    )

    assert result["allowed"] is True
    assert result["limit"] == -1
    redis.incr.assert_not_called()
