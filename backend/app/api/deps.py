"""Dependency injection for API routes."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.database import get_async_session

# ─── Settings ──────────────────────────────────────────────────────────────────


def get_config() -> Settings:
    """Return the application config."""
    return get_settings()


ConfigDep = Annotated[Settings, Depends(get_config)]

# ─── Database ──────────────────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async for session in get_async_session():
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db)]

# ─── Redis ─────────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis(config: ConfigDep) -> aioredis.Redis:
    """Return a Redis connection from pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(config.redis_url, decode_responses=True)
    return _redis_pool


RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]

# ─── Auth ──────────────────────────────────────────────────────────────────────


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Validate JWT and return user context.

    Stub implementation — will be replaced with Supabase JWT validation.
    Returns a dict with at minimum {id, email, tier} keys.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid authorization header"},
        )

    # TODO(kasey, 2026-02-14): Replace with actual Supabase JWT validation
    # For now, return a stub user for development
    # Try to decode email from token (assuming unencrypted JWT for dev)
    import jwt
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, options={"verify_signature": False})
        email = payload.get("email", "dev@arbiter.local")
    except Exception:
        email = "dev@arbiter.local"

    return {
        "id": uuid.uuid4(),
        "email": email,
        "tier": "PRO",
        "role": "ADMIN",  # Dev stub — all dev users are admins
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]

# ─── Convenience aliases used by routes ────────────────────────────────────────

DbSession = DBSession
GetSettings = ConfigDep
