"""users.py — User profile management routes.

Provides endpoints for the current user to view and update their
profile, and to delete their account (soft-delete or hard-delete).

Endpoints:
    GET    /api/v1/users/me     → Get current user's profile
    PATCH  /api/v1/users/me     → Update profile (name, etc.)
    DELETE /api/v1/users/me     → Delete account

Called by: Frontend settings page (save profile, delete account buttons).
Depends on: deps.py (CurrentUser, DbSession),
            tables.py (User)

Architecture note for AI agents:
    The settings page previously had non-functional Save/Delete buttons.
    These endpoints wire those buttons to actual backend logic. The
    frontend calls these via api.ts (updateProfile, deleteAccount methods).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])
logger = logging.getLogger(__name__)


# ─── Schemas ───────────────────────────────────────────────────────────────────


class UpdateProfileRequest(BaseModel):
    """Request body for updating user profile.

    Fields:
        name: New display name for the user. Optional — omit to leave unchanged.
    """

    name: str | None = None


class ProfileResponse(BaseModel):
    """Response shape for user profile.

    Returned by GET /users/me and PATCH /users/me.
    """

    id: str
    email: str
    name: str | None
    role: str


# ─── Get My Profile ──────────────────────────────────────────────────────────


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: CurrentUser, db: DbSession) -> ProfileResponse:
    """Get the current user's profile.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Returns:
        User profile with id, email, name, and role.

    Raises:
        HTTPException: 404 if user record not found (shouldn't happen since
        deps.py upserts the user, but defensive coding).
    """
    result = await db.execute(select(User).where(User.id == user["id"]))
    user_record = result.scalar_one_or_none()

    if not user_record:
        raise HTTPException(status_code=404, detail="User not found.")

    return ProfileResponse(
        id=str(user_record.id),
        email=user_record.email,
        name=user_record.name,
        role=user_record.role or "USER",
    )


# ─── Update Profile ──────────────────────────────────────────────────────────


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(body: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> ProfileResponse:
    """Update the current user's profile.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Args:
        body: Fields to update (currently only `name`).

    Returns:
        Updated user profile.

    Raises:
        HTTPException: 400 if no fields provided, 404 if user not found.
    """
    if body.name is None:
        raise HTTPException(status_code=400, detail="No updateable fields provided.")

    result = await db.execute(select(User).where(User.id == user["id"]))
    user_record = result.scalar_one_or_none()

    if not user_record:
        raise HTTPException(status_code=404, detail="User not found.")

    if body.name is not None:
        user_record.name = body.name

    await db.commit()
    await db.refresh(user_record)

    logger.info("Profile updated: user=%s name=%s", user_record.id, user_record.name)

    return ProfileResponse(
        id=str(user_record.id),
        email=user_record.email,
        name=user_record.name,
        role=user_record.role or "USER",
    )


# ─── Delete Account ─────────────────────────────────────────────────────────


@router.delete("/me", status_code=204)
async def delete_account(user: CurrentUser, db: DbSession) -> None:
    """Delete the current user's account.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    WHY hard-delete: For GDPR compliance, we fully remove the user
    record and rely on cascade deletes for related data (sessions,
    library entries, rulings, party memberships, subscriptions).

    WARNING: This is irreversible. The frontend shows a confirmation
    dialog before calling this endpoint.

    Raises:
        HTTPException: 404 if user not found.
    """
    result = await db.execute(select(User).where(User.id == user["id"]))
    user_record = result.scalar_one_or_none()

    if not user_record:
        raise HTTPException(status_code=404, detail="User not found.")

    await db.delete(user_record)
    await db.commit()
    logger.info("Account deleted: user=%s email=%s", user["id"], user["email"])
