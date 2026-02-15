"""Dependency injection for API routes.

Provides FastAPI dependencies for configuration, database sessions,
Redis connections, and JWT-based authentication. The auth dependency
validates NextAuth JWTs and upserts users into the local database.

Called by: All route modules via type aliases (CurrentUser, DbSession, etc.)
Depends on: config.py, models/database.py, models/tables.py
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.database import get_async_session
from app.models.tables import Subscription, User

logger = logging.getLogger(__name__)

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
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate NextAuth JWT and return user context.

    Decodes the JWT from the Authorization header, verifies the signature
    using NEXTAUTH_SECRET, and upserts the user into the local database.
    Returns a dict with {id, email, name, tier, role} keys.

    Args:
        authorization: Bearer token from the Authorization header.
        db: Async database session for user upsert.

    Returns:
        Dict with user context: id (UUID), email, name, tier, role.

    Raises:
        HTTPException: 401 if token is missing, malformed, or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid authorization header"},
        )

    token = authorization.split(" ", 1)[1]
    settings = get_settings()

    # WHY: Any mode besides mock must enforce signature verification.
    # Allowing unsigned JWTs in sandbox makes admin/user auth trivially forgeable.
    if not settings.nextauth_secret:
        if settings.is_mock:
            # Real routes are not mounted in mock mode, but keep this defensive fallback.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Auth is bypassed only in mock mode"},
            )
        logger.error("NEXTAUTH_SECRET/AUTH_SECRET not set — rejecting auth tokens")
        raise HTTPException(
            status_code=503,
            detail="The Arbiter can't verify your credentials right now. Please try again later!",
        )

    try:
        # NextAuth uses HS256 JWTs signed with NEXTAUTH_SECRET
        payload = jwt.decode(token, settings.nextauth_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "Authentication token has expired"},
        ) from None
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid authentication token"},
        ) from exc

    # Extract user identity from NextAuth JWT payload
    # NextAuth puts user id in 'sub', email in 'email', name in 'name'
    email = payload.get("email")
    sub = payload.get("sub")  # NextAuth user ID
    name = payload.get("name")

    if not email and not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token missing user identity"},
        )

    # Upsert user into local database — find by email first, then by sub
    user_record = None
    if email:
        result = await db.execute(select(User).where(User.email == email))
        user_record = result.scalar_one_or_none()

    if user_record is None and sub:
        # Try to find by the NextAuth sub (stored as string ID)
        try:
            sub_uuid = uuid.UUID(sub)
            result = await db.execute(select(User).where(User.id == sub_uuid))
            user_record = result.scalar_one_or_none()
        except ValueError:
            pass  # sub is not a UUID, skip

    if user_record is None:
        # First login — create user record
        # Prefer stable UUID from token sub when possible to avoid duplicate users.
        user_id = uuid.uuid4()
        if sub:
            try:
                user_id = uuid.UUID(sub)
            except ValueError:
                pass
        user_record = User(
            id=user_id,
            email=email or f"{sub}@arbiter.local",
            name=name,
            role="USER",
        )
        db.add(user_record)
        await db.flush()
        logger.info("Created new user: email=%s id=%s", user_record.email, user_record.id)
    else:
        # Update name if changed
        if name and user_record.name != name:
            user_record.name = name
            await db.flush()

    # Resolve subscription tier
    tier = "FREE"
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_record.id,
            func.lower(Subscription.status) == "active",
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription:
        tier = subscription.plan_tier

    await db.commit()

    return {
        "id": user_record.id,
        "email": user_record.email,
        "name": user_record.name,
        "tier": tier,
        "role": user_record.role or "USER",
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]

# ─── Convenience aliases used by routes ────────────────────────────────────────

DbSession = DBSession
GetSettings = ConfigDep
