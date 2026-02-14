import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.tables import OfficialRuleset

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

class CatalogEntry(BaseModel):
    id: uuid.UUID
    game_name: str
    game_slug: str
    publisher_name: str
    version: str
    status: str

@router.get("/", response_model=list[CatalogEntry])
async def list_verified_games(
    db: AsyncSession = Depends(get_db),
):
    # List official rulesets where publisher is verified (optional constraint)
    # For now, just list all OfficialRulesets that are READY?
    # Or just list all existing ones.

    stmt = (
        select(OfficialRuleset)
        .options(selectinload(OfficialRuleset.publisher))
        #.where(OfficialRuleset.status == "READY") # Uncomment when using real statuses
    )
    result = await db.execute(stmt)
    rulesets = result.scalars().all()

    return [
        CatalogEntry(
            id=r.id,
            game_name=r.game_name,
            game_slug=r.game_slug,
            publisher_name=r.publisher.name,
            version=r.version,
            status=r.status,
        )
        for r in rulesets
    ]
