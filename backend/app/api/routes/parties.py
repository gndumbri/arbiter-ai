"""parties.py — Party management for shared game session history.

Players create parties (groups), invite friends, and share rulings
within the party. Parties enable the PARTY privacy level on saved rulings.

Called by: Frontend parties page (/dashboard/parties)
Depends on: deps.py (CurrentUser, DbSession), tables.py (Party, PartyMember)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.tables import Party, PartyMember

router = APIRouter(prefix="/api/v1/parties", tags=["parties"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class CreatePartyRequest(BaseModel):
    """Request body for creating a new party."""

    name: str


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
async def create_party(body: CreatePartyRequest, user: CurrentUser, db: DbSession) -> PartyResponse:
    """Create a new party. The creator becomes the OWNER.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers (FREE, PRO, ADMIN).

    Args:
        body: Party creation data with a name.

    Returns:
        The created party with member_count=1 (the owner).
    """
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
) -> dict:
    """Join a party as a MEMBER.

    Auth: JWT required.
    Rate limit: None.
    Tier: All tiers.

    Args:
        party_id: UUID of the party to join.

    Returns:
        Confirmation dict with party_id and status.

    Raises:
        HTTPException: 404 if party not found, 409 if already a member.
    """
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
