"""parties.py — Party management for shared game session history.

Players create parties (groups), invite friends, and share rulings
within the party. Parties enable the PARTY privacy level on saved rulings.

Called by: Frontend parties page (/dashboard/parties)
Depends on: deps.py (CurrentUser, DbSession), tables.py (Party, PartyMember)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limit import RateLimitDep
from app.config import get_settings
from app.models.tables import Party, PartyGameShare, PartyMember

router = APIRouter(prefix="/api/v1/parties", tags=["parties"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class CreatePartyRequest(BaseModel):
    """Request body for creating a new party."""

    name: str = Field(..., min_length=1, max_length=100)


class PartyResponse(BaseModel):
    """Response shape for a party."""

    id: str
    name: str
    owner_id: str
    member_count: int
    created_at: str | None


class PartyMemberResponse(BaseModel):
    """Response shape for a party member."""

    user_id: str
    role: str  # "OWNER" | "MEMBER"
    joined_at: str | None


# ─── Create Party ─────────────────────────────────────────────────────────────


@router.post("", response_model=PartyResponse, status_code=201)
async def create_party(
    body: CreatePartyRequest,
    user: CurrentUser,
    db: DbSession,
    limiter: RateLimitDep,
) -> PartyResponse:
    """Create a new party. The creator becomes the OWNER.

    Auth: JWT required.
    Rate limit: FREE=5/hour, PRO=20/hour.
    Tier: All tiers (FREE, PRO, ADMIN).

    Args:
        body: Party creation data with a name.

    Returns:
        The created party with member_count=1 (the owner).
    """
    # Enforce per-user hourly party creation limit
    await limiter.check_and_increment(
        user_id=str(user["id"]),
        tier=user["tier"],
        category="party",
    )

    party = Party(
        name=body.name,
        owner_id=user["id"],
    )
    db.add(party)
    # Flush to get the party ID before creating the membership
    await db.flush()

    # The creator is automatically added as OWNER
    member = PartyMember(
        party_id=party.id,
        user_id=user["id"],
        role="OWNER",
    )
    db.add(member)
    await db.commit()
    await db.refresh(party)

    return PartyResponse(
        id=str(party.id),
        name=party.name,
        owner_id=str(party.owner_id),
        member_count=1,
        created_at=party.created_at.isoformat() if party.created_at else None,
    )


# ─── List My Parties ──────────────────────────────────────────────────────────


@router.get("", response_model=list[PartyResponse])
async def list_my_parties(user: CurrentUser, db: DbSession) -> list[PartyResponse]:
    """List parties the current user belongs to.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Returns:
        List of parties the user is a member of, with member counts.
    """
    result = await db.execute(
        select(PartyMember).where(PartyMember.user_id == user["id"])
    )
    memberships = result.scalars().all()

    # TODO(kasey, 2026-02-14): Replace N+1 queries with a single JOIN query
    # for better performance at scale. Fine for MVP with small party counts.
    parties = []
    for m in memberships:
        party_result = await db.execute(
            select(Party).where(Party.id == m.party_id)
        )
        party = party_result.scalar_one_or_none()
        if party:
            member_count_result = await db.execute(
                select(PartyMember).where(PartyMember.party_id == party.id)
            )
            member_count = len(member_count_result.scalars().all())
            parties.append(
                PartyResponse(
                    id=str(party.id),
                    name=party.name,
                    owner_id=str(party.owner_id),
                    member_count=member_count,
                    created_at=party.created_at.isoformat() if party.created_at else None,
                )
            )

    return parties


# ─── List Party Members ───────────────────────────────────────────────────────


@router.get("/{party_id}/members", response_model=list[PartyMemberResponse])
async def list_party_members(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[PartyMemberResponse]:
    """List members of a party (must be a member to view).

    Auth: JWT required (members only — prevents data leakage).
    Rate limit: None.
    Tier: All tiers.

    Args:
        party_id: UUID of the party whose members to list.

    Returns:
        List of party members with roles and join dates.

    Raises:
        HTTPException: 403 if caller is not a member of the party.
    """
    # Membership gate: only party members can see the member list
    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this party")

    result = await db.execute(
        select(PartyMember).where(PartyMember.party_id == party_id)
    )
    members = result.scalars().all()

    return [
        PartyMemberResponse(
            user_id=str(m.user_id),
            role=m.role,
            joined_at=m.joined_at.isoformat() if m.joined_at else None,
        )
        for m in members
    ]


# ─── Join Party ────────────────────────────────────────────────────────────────


@router.post("/{party_id}/join", status_code=201)
async def join_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limiter: RateLimitDep,
) -> dict:
    """Join a party as a MEMBER.

    Auth: JWT required.
    Rate limit: FREE=5/hour, PRO=20/hour.
    Tier: All tiers.

    Args:
        party_id: UUID of the party to join.

    Returns:
        Confirmation dict with party_id and status.

    Raises:
        HTTPException: 404 if party not found, 409 if already a member.
    """
    # --- Enforce party action rate limit ---
    await limiter.check_and_increment(
        user_id=str(user["id"]),
        tier=user["tier"],
        category="party",
    )

    # --- Validate party exists ---
    party_result = await db.execute(select(Party).where(Party.id == party_id))
    party = party_result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    # --- Prevent duplicate membership ---
    existing = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already a member")

    member = PartyMember(
        party_id=party_id,
        user_id=user["id"],
        role="MEMBER",
    )
    db.add(member)
    await db.commit()

    return {"party_id": str(party_id), "status": "joined"}


# ─── Leave Party ───────────────────────────────────────────────────────────────


@router.post("/{party_id}/leave", status_code=200)
async def leave_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Leave a party. Owners cannot leave (must transfer ownership first).

    Auth: JWT required (members only).
    Rate limit: None.
    Tier: All tiers.

    Args:
        party_id: UUID of the party to leave.

    Returns:
        Confirmation dict with party_id and status.

    Raises:
        HTTPException: 400 if user is the owner, 404 if not a member.
    """
    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Not a member")

    # Owners must transfer ownership before leaving to prevent orphaned parties
    if membership.role == "OWNER":
        raise HTTPException(status_code=400, detail="Owners cannot leave. Transfer ownership first.")

    await db.delete(membership)
    await db.commit()

    return {"party_id": str(party_id), "status": "left"}


# ─── Delete Party ──────────────────────────────────────────────────────────────


@router.delete("/{party_id}", status_code=204)
async def delete_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a party and all its memberships (owner only).

    Auth: JWT required (owner only).
    Rate limit: None.
    Tier: All tiers.

    Args:
        party_id: UUID of the party to delete.

    Raises:
        HTTPException: 403 if caller is not the party owner, 404 if not found.
    """
    result = await db.execute(select(Party).where(Party.id == party_id))
    party = result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can delete a party")

    # CASCADE: PartyMember rows are deleted via FK cascade in the schema
    await db.delete(party)
    await db.commit()


# ─── Generate Invite Link ────────────────────────────────────────────────────


@router.get("/{party_id}/invite", response_model=dict)
async def create_invite_link(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Generate a shareable invite link valid for 48 hours.

    WHY: Stateless invite system — we sign a JWT with the party_id
    rather than storing invites in the database. The token is
    self-contained and self-expiring.

    Auth: JWT required (members only — prevents link leakage).
    Returns: invite_url + expiry timestamp.
    """

    # Security: only party members can generate invite links
    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this party")

    settings = get_settings()
    if not settings.nextauth_secret:
        raise HTTPException(status_code=503, detail="Invite signing is not configured.")
    expires = datetime.now(UTC) + timedelta(hours=48)

    payload = {
        "sub": "party_invite",
        "party_id": str(party_id),
        "invited_by": str(user["id"]),
        "exp": expires,
    }
    token = pyjwt.encode(payload, settings.nextauth_secret, algorithm="HS256")

    # Use canonical app URL for share links (separate from CORS list).
    base_url = settings.normalized_app_base_url

    return {
        "invite_url": f"{base_url}/invite/{token}",
        "expires_at": expires.isoformat(),
    }


# ─── Join via Invite Link ────────────────────────────────────────────────────


class JoinViaLinkRequest(BaseModel):
    """Request body for joining a party via an invite token."""

    token: str


@router.post("/join-via-link", status_code=201)
async def join_via_invite_link(
    body: JoinViaLinkRequest,
    user: CurrentUser,
    db: DbSession,
    limiter: RateLimitDep,
) -> dict:
    """Join a party using a signed invite token.

    WHY: The invite token is a self-contained JWT — we decode it,
    extract the party_id, and reuse the existing join logic.

    Auth: JWT required (user must be logged in to join).
    Raises: 400 if expired, 404 if party gone, 409 if already member.
    """

    settings = get_settings()
    if not settings.nextauth_secret:
        raise HTTPException(status_code=503, detail="Invite verification is not configured.")
    try:
        payload = pyjwt.decode(
            body.token, settings.nextauth_secret, algorithms=["HS256"]
        )
        if payload.get("sub") != "party_invite":
            raise pyjwt.InvalidTokenError
        party_id = uuid.UUID(payload["party_id"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=400, detail="Invite link has expired"
        ) from None
    except (pyjwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail="Invalid invite link"
        ) from None

    # Reuse the existing join_party logic (validates party exists + no dupes)
    return await join_party(party_id, user, db, limiter)


# ─── Remove Member ────────────────────────────────────────────────────────────


@router.delete("/{party_id}/members/{user_id}", status_code=200)
async def remove_member(
    party_id: uuid.UUID,
    user_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Remove a member from a party (owner only).

    WHY: Owners need to manage who's in the group — e.g., remove
    someone who left the gaming group or was disruptive.
    Users can remove themselves via POST /{party_id}/leave.

    Auth: JWT required (owner only).
    """
    # Verify caller is the party owner
    party_result = await db.execute(select(Party).where(Party.id == party_id))
    party = party_result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can remove members")

    # Can't remove yourself (use leave instead)
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Use the leave endpoint to remove yourself")

    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member")

    # Also clean up their game shares
    shares_result = await db.execute(
        select(PartyGameShare).where(
            PartyGameShare.party_id == party_id,
            PartyGameShare.user_id == user_id,
        )
    )
    for share in shares_result.scalars().all():
        await db.delete(share)

    await db.delete(membership)
    await db.commit()

    return {"status": "removed", "user_id": str(user_id)}


# ─── Transfer Ownership ──────────────────────────────────────────────────────


class TransferOwnershipRequest(BaseModel):
    """Request body for transferring party ownership."""

    new_owner_id: str


@router.patch("/{party_id}/owner", status_code=200)
async def transfer_ownership(
    party_id: uuid.UUID,
    body: TransferOwnershipRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Transfer party ownership to another member.

    WHY: Without this, the original creator can never leave the party
    because owners can't leave. This lets them hand off to someone else.

    Auth: JWT required (current owner only).
    """
    party_result = await db.execute(select(Party).where(Party.id == party_id))
    party = party_result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can transfer ownership")

    new_owner_id = uuid.UUID(body.new_owner_id)

    # Verify the new owner is actually a member
    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == new_owner_id,
        )
    )
    new_owner_member = result.scalar_one_or_none()
    if not new_owner_member:
        raise HTTPException(status_code=404, detail="New owner must be a member of the party")

    # Swap roles
    old_owner_result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    old_owner_member = old_owner_result.scalar_one()
    old_owner_member.role = "MEMBER"
    new_owner_member.role = "OWNER"
    party.owner_id = new_owner_id

    await db.commit()

    return {"status": "transferred", "new_owner_id": str(new_owner_id)}


# ─── Game Shares (per-game visibility) ────────────────────────────────────────


@router.get("/{party_id}/game-shares", response_model=list[dict])
async def list_game_shares(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """List all game shares for a party.

    WHY: Each member chooses which games' Q&A the party can see.
    This endpoint returns all shares for the party so the UI
    can show who's sharing what.

    Auth: JWT required (members only).
    """
    # Verify caller is a member
    member_result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this party")

    result = await db.execute(
        select(PartyGameShare).where(PartyGameShare.party_id == party_id)
    )
    shares = result.scalars().all()

    return [
        {"game_name": s.game_name, "user_id": str(s.user_id)}
        for s in shares
    ]


class UpdateGameSharesRequest(BaseModel):
    """Request body for updating game shares."""

    game_names: list[str]


@router.put("/{party_id}/game-shares", status_code=200)
async def update_game_shares(
    party_id: uuid.UUID,
    body: UpdateGameSharesRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Set which games the current user shares with the party.

    WHY: Users control their own privacy — they pick which games'
    rulings the party can see. This replaces all existing shares
    for this user+party with the new list.

    Auth: JWT required (members only).
    """
    # Verify caller is a member
    member_result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this party")

    # Delete existing shares for this user+party
    existing = await db.execute(
        select(PartyGameShare).where(
            PartyGameShare.party_id == party_id,
            PartyGameShare.user_id == user["id"],
        )
    )
    for share in existing.scalars().all():
        await db.delete(share)

    # Insert new shares
    for game_name in body.game_names:
        db.add(PartyGameShare(
            party_id=party_id,
            user_id=user["id"],
            game_name=game_name,
        ))

    await db.commit()

    return {"status": "updated", "game_count": len(body.game_names)}
