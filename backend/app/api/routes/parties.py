"""Party routes — Create/Join groups for shared game session history.

Players can create parties, invite others, and share rulings within the party.
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
    name: str


class PartyResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    member_count: int
    created_at: str | None


class PartyMemberResponse(BaseModel):
    user_id: str
    role: str
    joined_at: str | None


# ─── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=PartyResponse, status_code=201)
async def create_party(body: CreatePartyRequest, user: CurrentUser, db: DbSession) -> PartyResponse:
    """Create a new party. The creator becomes the OWNER."""
    party = Party(
        name=body.name,
        owner_id=user["id"],
    )
    db.add(party)
    await db.flush()

    # Add creator as owner
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


@router.get("", response_model=list[PartyResponse])
async def list_my_parties(user: CurrentUser, db: DbSession) -> list[PartyResponse]:
    """List parties the current user belongs to."""
    result = await db.execute(
        select(PartyMember).where(PartyMember.user_id == user["id"])
    )
    memberships = result.scalars().all()

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


@router.get("/{party_id}/members", response_model=list[PartyMemberResponse])
async def list_party_members(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[PartyMemberResponse]:
    """List members of a party (must be a member to view)."""
    # Check membership
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


@router.post("/{party_id}/join", status_code=201)
async def join_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Join a party."""
    # Check party exists
    party_result = await db.execute(select(Party).where(Party.id == party_id))
    party = party_result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    # Check already a member
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


@router.post("/{party_id}/leave", status_code=200)
async def leave_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Leave a party. Owners cannot leave (must transfer ownership first)."""
    result = await db.execute(
        select(PartyMember).where(
            PartyMember.party_id == party_id,
            PartyMember.user_id == user["id"],
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Not a member")

    if membership.role == "OWNER":
        raise HTTPException(status_code=400, detail="Owners cannot leave. Transfer ownership first.")

    await db.delete(membership)
    await db.commit()

    return {"party_id": str(party_id), "status": "left"}


@router.delete("/{party_id}", status_code=204)
async def delete_party(
    party_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a party (owner only)."""
    result = await db.execute(select(Party).where(Party.id == party_id))
    party = result.scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    if party.owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="Only the owner can delete a party")

    await db.delete(party)
    await db.commit()
