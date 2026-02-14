"""Redis-backed rate limiting dependency.

Uses a sliding window counter in Redis to enforce daily query limits
based on the user's subscription tier.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import HTTPException

from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-backed rate limiter using daily sliding windows."""

    def __init__(self, redis: aioredis.Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def check_and_increment(
        self,
        user_id: str,
        tier: str = "FREE",
    ) -> dict:
        """Check if user is within daily limit and increment counter.

        Returns dict with 'allowed', 'remaining', 'limit', 'reset_at'.
        Raises HTTPException(429) if limit exceeded.
        """
        # Get tier limits (could be from DB in production)
        limits = {
            "FREE": 5,
            "PRO": -1,  # -1 = unlimited
            "ADMIN": -1,
        }
        daily_limit = limits.get(tier, 5)

        # Unlimited tier — always allow
        if daily_limit == -1:
            return {
                "allowed": True,
                "remaining": -1,
                "limit": -1,
                "reset_at": None,
            }

        # Build Redis key for today
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        key = f"rate_limit:{user_id}:{today}"

        # Increment counter
        current = await self._redis.incr(key)

        # Set TTL on first request (expire at end of day)
        if current == 1:
            # Set expiry to 24 hours from now (simpler than exact midnight)
            await self._redis.expire(key, 86400)

        remaining = max(0, daily_limit - current)
        ttl = await self._redis.ttl(key)

        if current > daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Daily query limit ({daily_limit}) exceeded. Upgrade to Pro for unlimited queries.",
                    "remaining": 0,
                    "limit": daily_limit,
                    "reset_seconds": ttl,
                },
            )

        return {
            "allowed": True,
            "remaining": remaining,
            "limit": daily_limit,
            "reset_seconds": ttl,
        }


async def get_rate_limiter(
    redis: aioredis.Redis,
    settings: Settings,
) -> RateLimiter:
    """Factory for the rate limiter."""
    return RateLimiter(redis=redis, settings=settings)
