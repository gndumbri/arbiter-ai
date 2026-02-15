"""rate_limit.py — Redis-backed rate limiting for query endpoints.

Uses a sliding-window daily counter in Redis to enforce per-user
query limits based on subscription tier. FREE users get 5 queries/day,
PRO and ADMIN users get unlimited access.

Called by: judge.py (can be used as dependency injection)
Depends on: Redis (via deps.py), config.py (Settings)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import HTTPException

from app.config import Settings

logger = logging.getLogger(__name__)

# Daily query limits per subscription tier.
# -1 means unlimited. These are defaults; production should pull from
# the SubscriptionTier table for live configurability.
TIER_LIMITS: dict[str, int] = {
    "FREE": 5,
    "PRO": -1,  # unlimited
    "ADMIN": -1,  # unlimited
}


class RateLimiter:
    """Redis-backed rate limiter using daily sliding windows.

    Each user gets a Redis key per day (rate_limit:{user_id}:{date}).
    The key auto-expires after 24 hours. Counters are atomic via INCR.
    """

    def __init__(self, redis: aioredis.Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def check_and_increment(
        self,
        user_id: str,
        tier: str = "FREE",
    ) -> dict:
        """Check if user is within daily limit and increment counter.

        Args:
            user_id: The user's UUID string.
            tier: Subscription tier (FREE, PRO, ADMIN).

        Returns:
            Dict with 'allowed' (bool), 'remaining' (int), 'limit' (int),
            and 'reset_seconds' (int or None).

        Raises:
            HTTPException: 429 if daily limit exceeded for the user's tier.
        """
        daily_limit = TIER_LIMITS.get(tier, 5)

        # Unlimited tiers bypass Redis entirely for performance
        if daily_limit == -1:
            return {
                "allowed": True,
                "remaining": -1,
                "limit": -1,
                "reset_at": None,
            }

        # Build Redis key scoped to user + calendar day (UTC)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        key = f"rate_limit:{user_id}:{today}"

        # Atomic increment — safe for concurrent requests
        current = await self._redis.incr(key)

        # Set TTL only on the first request of the day (when INCR creates the key)
        if current == 1:
            await self._redis.expire(key, 86400)  # 24h TTL

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
    """Factory for the rate limiter (for use as a FastAPI dependency).

    Args:
        redis: Async Redis connection from the connection pool.
        settings: Application settings.

    Returns:
        A configured RateLimiter instance.
    """
    return RateLimiter(redis=redis, settings=settings)
