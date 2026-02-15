"""abuse_detection.py — Behavioral abuse detection via Redis.

Detects abnormal request patterns and temporarily blocks abusive
users or IPs. Designed to catch scripted/bot abuse that per-endpoint
rate limits might miss.

Detection patterns:
    1. Burst detection   — >20 requests in 10 seconds → 5 min block
    2. Upload velocity   — >5 uploads in 5 minutes → 30 min upload block
    3. Harvest detection  — >50 data reads in 1 minute → 10 min block

Blocks are stored in Redis with auto-expiring keys:
    abuse:block:{user_id_or_ip}:{category}

Called by: Route modules (check before expensive operations)
Depends on: Redis (via deps.py)
"""

from __future__ import annotations

import logging
import time

import redis.asyncio as aioredis
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ─── Detection Thresholds ─────────────────────────────────────────────────────

class AbuseThreshold:
    """Configuration for a single abuse detection pattern."""

    def __init__(
        self,
        name: str,
        max_events: int,
        window_seconds: int,
        block_seconds: int,
        message: str,
    ) -> None:
        self.name = name
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.message = message


# WHY: These thresholds are intentionally generous for normal users.
# A real person won't make 20 requests in 10 seconds or upload 5
# files in 5 minutes. These catch automated scripts and bots.
THRESHOLDS = {
    "burst": AbuseThreshold(
        name="burst",
        max_events=20,
        window_seconds=10,
        block_seconds=300,  # 5 minutes
        message="Whoa there! You're moving faster than a speed-run. Please wait a few minutes.",
    ),
    "upload_velocity": AbuseThreshold(
        name="upload_velocity",
        max_events=5,
        window_seconds=300,  # 5 minutes
        block_seconds=1800,  # 30 minutes
        message="Too many uploads too fast. Please wait before uploading more rulebooks.",
    ),
    "harvest": AbuseThreshold(
        name="harvest",
        max_events=50,
        window_seconds=60,
        block_seconds=600,  # 10 minutes
        message="Unusual reading pattern detected. Please slow down your requests.",
    ),
}


class AbuseDetector:
    """Redis-backed abuse pattern detector.

    Uses Redis sorted sets with timestamps as scores for efficient
    sliding-window event tracking. Each event is recorded with its
    timestamp, and expired events are pruned on every check.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def is_blocked(self, identifier: str, category: str = "burst") -> bool:
        """Check if an identifier (user ID or IP) is currently blocked.

        Args:
            identifier: User ID or IP address.
            category: Abuse category to check.

        Returns:
            True if the identifier is currently blocked.
        """
        key = f"abuse:block:{identifier}:{category}"
        return await self._redis.exists(key) > 0

    async def record_and_check(
        self,
        identifier: str,
        category: str = "burst",
    ) -> None:
        """Record an event and check if the threshold is exceeded.

        If the threshold is exceeded, the identifier is blocked for
        the configured duration and an HTTPException is raised.

        Args:
            identifier: User ID or IP address.
            category: Abuse category (burst, upload_velocity, harvest).

        Raises:
            HTTPException: 429 if the identifier is blocked or threshold exceeded.
        """
        threshold = THRESHOLDS.get(category)
        if threshold is None:
            return

        # Check existing block first
        block_key = f"abuse:block:{identifier}:{category}"
        block_ttl = await self._redis.ttl(block_key)
        if block_ttl > 0:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "ABUSE_BLOCKED",
                    "message": threshold.message,
                    "retry_after_seconds": block_ttl,
                },
            )

        # Record event in sliding window (sorted set with timestamp scores)
        events_key = f"abuse:events:{identifier}:{category}"
        now = time.time()
        window_start = now - threshold.window_seconds

        # WHY: Pipeline for atomicity — add event + prune old + count + set TTL
        pipe = self._redis.pipeline()
        pipe.zadd(events_key, {f"{now}": now})  # Add current event
        pipe.zremrangebyscore(events_key, 0, window_start)  # Prune expired
        pipe.zcard(events_key)  # Count events in window
        pipe.expire(events_key, threshold.window_seconds * 2)  # Cleanup TTL
        results = await pipe.execute()

        event_count = results[2]

        if event_count > threshold.max_events:
            # Block the identifier
            await self._redis.setex(block_key, threshold.block_seconds, "1")
            # Clear the events set since we've already blocked
            await self._redis.delete(events_key)

            logger.warning(
                "Abuse detected — blocking",
                extra={
                    "identifier": identifier,
                    "category": category,
                    "event_count": event_count,
                    "block_seconds": threshold.block_seconds,
                },
            )

            raise HTTPException(
                status_code=429,
                detail={
                    "code": "ABUSE_BLOCKED",
                    "message": threshold.message,
                    "retry_after_seconds": threshold.block_seconds,
                },
            )

    async def check_upload_velocity(self, user_id: str) -> None:
        """Convenience wrapper for upload velocity checks."""
        await self.record_and_check(user_id, "upload_velocity")

    async def check_burst(self, identifier: str) -> None:
        """Convenience wrapper for general burst checks."""
        await self.record_and_check(identifier, "burst")

    async def check_harvest(self, identifier: str) -> None:
        """Convenience wrapper for data harvesting checks."""
        await self.record_and_check(identifier, "harvest")
