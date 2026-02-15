"""Unit tests for abuse detector resilience behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.api.abuse_detection import AbuseDetector


@pytest.mark.anyio
async def test_abuse_detector_record_and_check_allows_when_redis_unavailable() -> None:
    """Abuse detector should fail-open when Redis is unavailable."""
    redis = AsyncMock()
    redis.ttl.side_effect = RedisError("redis unavailable")

    detector = AbuseDetector(redis=redis)
    await detector.record_and_check(identifier="user-1", category="upload_velocity")


@pytest.mark.anyio
async def test_abuse_detector_is_blocked_returns_false_when_redis_unavailable() -> None:
    """is_blocked should fail-open to False if Redis is unavailable."""
    redis = AsyncMock()
    redis.exists.side_effect = RedisError("redis unavailable")

    detector = AbuseDetector(redis=redis)
    blocked = await detector.is_blocked(identifier="user-1", category="burst")

    assert blocked is False
