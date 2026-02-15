"""ip_rate_limit.py — IP-based rate limiting middleware.

Applies per-IP rate limiting at the middleware level (before auth),
catching unauthenticated abuse like brute-force login attempts,
catalog scraping, and health check spam.

Uses Redis sliding counters with a default of 100 requests/minute
per IP address. Adds standard rate-limit response headers.

WHY: This catches abuse from bots and scripts that don't authenticate.
The per-user rate limiter in rate_limit.py only kicks in AFTER auth,
so unauthenticated endpoints (catalog, health) would be unprotected
without this middleware layer.

Called by: main.py (via register_middleware)
Depends on: Redis (via configured URL), config.py (Settings)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
# Requests per minute per IP. Generous enough for normal browsing but
# catches automated scripts.
IP_RATE_LIMIT = 100
IP_RATE_WINDOW_SECONDS = 60

# Paths exempt from IP rate limiting (health checks, etc.)
EXEMPT_PATHS: set[str] = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Redis connection (lazy-initialized, shared across requests)
_ip_redis: aioredis.Redis | None = None


def _get_client_ip(request: Request) -> str:
    """Extract client IP with configurable trusted proxy handling.

    Security note:
    `X-Forwarded-For` is client-controlled unless it is set by trusted
    reverse proxies. We only read it when TRUSTED_PROXY_HOPS > 0 and then
    pick from the right side of the chain to avoid spoofed left-most values.
    """
    settings = get_settings()
    trusted_hops = max(0, settings.trusted_proxy_hops)
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded and trusted_hops > 0:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(parts) >= trusted_hops:
            # Example:
            # trusted_hops=1 (ALB) -> right-most entry
            # trusted_hops=2 -> second from right, etc.
            return parts[-trusted_hops]

    return request.client.host if request.client else "unknown"


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting middleware using Redis counters.

    Adds the following response headers on every request:
        X-RateLimit-Limit: 100
        X-RateLimit-Remaining: 87
        X-RateLimit-Reset: 45

    Returns 429 with Retry-After header when limit exceeded.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        global _ip_redis

        # Skip for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()

        # Skip in mock mode — no Redis available
        if settings.is_mock:
            return await call_next(request)

        # Lazy-initialize Redis connection
        if _ip_redis is None:
            try:
                _ip_redis = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
            except Exception:
                # If Redis is unavailable, let the request through
                logger.warning("IP rate limiter: Redis unavailable, skipping")
                return await call_next(request)

        client_ip = _get_client_ip(request)

        # Build time-windowed key (per-minute)
        now = datetime.now(UTC)
        window_key = now.strftime("%Y-%m-%dT%H:%M")
        key = f"ip_rate:{client_ip}:{window_key}"

        try:
            current = await _ip_redis.incr(key)
            if current == 1:
                await _ip_redis.expire(key, IP_RATE_WINDOW_SECONDS)

            ttl = await _ip_redis.ttl(key)
            remaining = max(0, IP_RATE_LIMIT - current)

            if current > IP_RATE_LIMIT:
                logger.warning(
                    "IP rate limit exceeded",
                    extra={"ip": client_ip, "count": current, "path": request.url.path},
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests. Please slow down and try again shortly.",
                        }
                    },
                    headers={
                        "Retry-After": str(ttl),
                        "X-RateLimit-Limit": str(IP_RATE_LIMIT),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                    },
                )

            # Normal request — add rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(IP_RATE_LIMIT)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(ttl)
            return response

        except Exception:
            # Redis failure should not block requests — fail open
            logger.warning("IP rate limiter: Redis error, allowing request")
            return await call_next(request)
