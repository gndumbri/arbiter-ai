"""rate_limit.py — Multi-category Redis-backed rate limiting.

Supports per-user rate limits across different endpoint categories
(queries, uploads, sessions, etc.) with tier-specific limits and
configurable time windows.

Each category uses a Redis key pattern:
    rate:{category}:{user_id}:{window_key}

The window_key depends on the window type:
    - "minute" → YYYY-MM-DDTHH:MM
    - "hour"   → YYYY-MM-DDTHH
    - "day"    → YYYY-MM-DD

Called by: Route modules via check_rate_limit() dependency
Depends on: Redis (via deps.py), config.py (Settings)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException
from redis.exceptions import RedisError

from app.api.deps import get_redis
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ─── Rate Limit Definitions ──────────────────────────────────────────────────
# Format: {category: {tier: (max_requests, window_type)}}
# -1 means unlimited. Window types: "minute", "hour", "day"
RATE_LIMITS: dict[str, dict[str, tuple[int, str]]] = {
    # LLM queries — most expensive, strictest limits
    "query": {
        "FREE": (5, "day"),
        "PRO": (-1, "day"),
        "ADMIN": (-1, "day"),
    },
    # PDF uploads — expensive (ingestion pipeline, storage, embedding)
    "upload": {
        "FREE": (3, "day"),
        "PRO": (20, "day"),
        "ADMIN": (-1, "day"),
    },
    # Session creation
    "session": {
        "FREE": (10, "day"),
        "PRO": (50, "day"),
        "ADMIN": (-1, "day"),
    },
    # Party operations (create, join)
    "party": {
        "FREE": (5, "hour"),
        "PRO": (20, "hour"),
        "ADMIN": (-1, "hour"),
    },
    # Ruling saves
    "ruling": {
        "FREE": (20, "day"),
        "PRO": (200, "day"),
        "ADMIN": (-1, "day"),
    },
    # General catch-all (billing, profile updates, etc.)
    "general": {
        "FREE": (30, "minute"),
        "PRO": (120, "minute"),
        "ADMIN": (-1, "minute"),
    },
}

# TTL per window type in seconds
_WINDOW_TTL: dict[str, int] = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}

# strftime format per window type
_WINDOW_FORMAT: dict[str, str] = {
    "minute": "%Y-%m-%dT%H:%M",
    "hour": "%Y-%m-%dT%H",
    "day": "%Y-%m-%d",
}


class RateLimiter:
    """Multi-category Redis-backed rate limiter.

    Each user gets a Redis counter per (category, window). Counters
    are atomic via INCR and auto-expire after one window period.
    """

    def __init__(self, redis: aioredis.Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def check_and_increment(
        self,
        user_id: str,
        tier: str = "FREE",
        category: str = "query",
    ) -> dict:
        """Check if user is within the limit for a category and increment.

        Args:
            user_id: The user's UUID string.
            tier: Subscription tier (FREE, PRO, ADMIN).
            category: Rate limit category (query, upload, session, etc.).

        Returns:
            Dict with 'allowed', 'remaining', 'limit', 'reset_seconds',
            and 'category' keys.

        Raises:
            HTTPException: 429 if limit exceeded for this category/tier.
        """
        category_limits = RATE_LIMITS.get(category, RATE_LIMITS["general"])
        limit_config = category_limits.get(tier, category_limits.get("FREE", (30, "minute")))
        max_requests, window_type = limit_config

        # Unlimited tiers bypass Redis entirely for performance
        if max_requests == -1:
            return {
                "allowed": True,
                "remaining": -1,
                "limit": -1,
                "reset_seconds": None,
                "category": category,
            }

        # Build Redis key scoped to user + category + time window
        now = datetime.now(UTC)
        window_key = now.strftime(_WINDOW_FORMAT[window_type])
        key = f"rate:{category}:{user_id}:{window_key}"

        try:
            # Atomic increment — safe for concurrent requests
            current = await self._redis.incr(key)

            # Set TTL only on the first request of the window
            if current == 1:
                await self._redis.expire(key, _WINDOW_TTL[window_type])

            remaining = max(0, max_requests - current)
            ttl = await self._redis.ttl(key)
        except RedisError as exc:
            logger.warning(
                "rate_limit_backend_unavailable; allowing request",
                extra={
                    "category": category,
                    "tier": tier,
                    "user_id": user_id,
                    "error": str(exc),
                },
            )
            # Fail-open to preserve core app availability if Redis is degraded.
            return {
                "allowed": True,
                "remaining": max_requests,
                "limit": max_requests,
                "reset_seconds": None,
                "category": category,
                "degraded": True,
            }

        if current > max_requests:
            # Build a user-friendly message based on category
            messages = {
                "query": f"You've used all {max_requests} questions for today. Upgrade to Pro for unlimited queries!",
                "upload": f"You've hit the daily upload limit ({max_requests}). Try again tomorrow or upgrade to Pro!",
                "session": f"You've created {max_requests} sessions today. Upgrade to Pro for more!",
                "party": f"Too many party actions this hour (limit: {max_requests}). Slow down a bit!",
                "ruling": f"You've saved {max_requests} rulings today. Upgrade to Pro for more!",
                "general": "You're making requests too quickly. Please wait a moment and try again.",
            }
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": messages.get(category, messages["general"]),
                    "remaining": 0,
                    "limit": max_requests,
                    "reset_seconds": ttl,
                    "category": category,
                },
            )

        return {
            "allowed": True,
            "remaining": remaining,
            "limit": max_requests,
            "reset_seconds": ttl,
            "category": category,
        }


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────


async def get_rate_limiter(
    redis: aioredis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RateLimiter:
    """Factory for the rate limiter (for use as a FastAPI dependency).

    Args:
        redis: Async Redis connection from the connection pool.
        settings: Application settings.

    Returns:
        A configured RateLimiter instance.
    """
    return RateLimiter(redis=redis, settings=settings)


# ─── Convenience dependency factories ─────────────────────────────────────────
# WHY: These create category-specific dependencies so routes can
# just add `_: UploadRateCheck` to their signature instead of
# manually calling check_and_increment().

RateLimitDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
"""Inject a RateLimiter instance. Call .check_and_increment() manually."""
