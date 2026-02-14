import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.tables import OfficialRuleset, Publisher

router = APIRouter(prefix="/api/v1/publishers", tags=["publishers"])

# Schemas (Internal for now, could move to schemas.py)
class PublisherCreate(BaseModel):
    name: str
    slug: str
    contact_email: EmailStr

class PublisherRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    contact_email: str
    verified: bool

class OfficialRulesetCreate(BaseModel):
    game_name: str
    game_slug: str
    version: str = "1.0"
    pinecone_namespace: str

class OfficialRulesetRead(BaseModel):
    id: uuid.UUID
    game_name: str
    game_slug: str
    version: str
    status: str
    chunk_count: int

@router.post("/", response_model=PublisherRead, status_code=status.HTTP_201_CREATED)
async def create_publisher(
    publisher: PublisherCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check if slug exists
    stmt = select(Publisher).where(Publisher.slug == publisher.slug)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publisher with this slug already exists",
        )

    # Create publisher
    # Note: api_key_hash should be generated here in a real app.
    # We'll put a placeholder for now.
    db_publisher = Publisher(
        name=publisher.name,
        slug=publisher.slug,
        contact_email=publisher.contact_email,
        api_key_hash="placeholder_hash",
        verified=False,
    )
    db.add(db_publisher)
    await db.commit()
    await db.refresh(db_publisher)
    return db_publisher

@router.get("/{publisher_id}", response_model=PublisherRead)
async def get_publisher(
    publisher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    publisher = await db.get(Publisher, publisher_id)
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")
    return publisher

@router.post("/{publisher_id}/games", response_model=OfficialRulesetRead, status_code=status.HTTP_201_CREATED)
async def create_official_ruleset(
    publisher_id: uuid.UUID,
    ruleset: OfficialRulesetCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify publisher exists
    publisher = await db.get(Publisher, publisher_id)
    if not publisher:
        raise HTTPException(status_code=404, detail="Publisher not found")

    # Check game slug uniqueness globally or per publisher?
    # Usually game slugs should be unique globally for the catalog.
    stmt = select(OfficialRuleset).where(OfficialRuleset.game_slug == ruleset.game_slug)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
         raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Game with this slug already exists",
        )

    db_ruleset = OfficialRuleset(
        publisher_id=publisher_id,
        game_name=ruleset.game_name,
        game_slug=ruleset.game_slug,
        version=ruleset.version,
        pinecone_namespace=ruleset.pinecone_namespace,
        status="CREATED", # Initial status
    )
    db.add(db_ruleset)
    await db.commit()
    await db.refresh(db_ruleset)
    return db_ruleset
