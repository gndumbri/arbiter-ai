"""catalog.py — Public game catalog browsing endpoints.

Lists official game rulesets from verified publishers. This is a
read-only public API — no auth required.

Endpoints:
    GET /api/v1/catalog/           → List all published rulesets
    GET /api/v1/catalog/{slug}     → Get a single ruleset by game slug

Called by: Frontend catalog page (CatalogPage component).
Depends on: deps.py (get_db), tables.py (OfficialRuleset, Publisher)

Architecture note for AI agents:
    The catalog lists OfficialRuleset entries that have been pushed by
    publishers via POST /publishers/{id}/games. The frontend catalog
    page merges these with COMMON_GAMES fallbacks. The slug-based detail
    endpoint is used when a user clicks on a game card.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.tables import OfficialRuleset

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


# ─── Schemas ───────────────────────────────────────────────────────────────────


class CatalogEntry(BaseModel):
    """Response shape for a catalog entry (used in list and detail views).

    Fields match the frontend CatalogEntry type in api.ts.
    """

    id: uuid.UUID
    game_name: str
    game_slug: str
    publisher_name: str
    version: str
    status: str


class CatalogDetailEntry(BaseModel):
    """Extended response for the detail view with additional metadata.

    Includes extra fields useful for the game detail page.
    """

    id: uuid.UUID
    game_name: str
    game_slug: str
    publisher_name: str
    version: str
    status: str
    chunk_count: int
    pinecone_namespace: str | None = None


# ─── List Catalog ─────────────────────────────────────────────────────────────


@router.get("/", response_model=list[CatalogEntry])
async def list_verified_games(
    db: AsyncSession = Depends(get_db),
):
    """List all official rulesets in the catalog.

    Auth: None (public endpoint).
    Rate limit: None.
    Tier: Open to all.

    Returns:
        List of catalog entries with game name, slug, publisher, version.

    Note: Currently lists ALL rulesets regardless of status. In production,
    uncomment the status filter to show only READY rulesets from verified
    publishers.
    """
    stmt = (
        select(OfficialRuleset)
        .options(selectinload(OfficialRuleset.publisher))
    )
    result = await db.execute(stmt)
    rulesets = result.scalars().all()

    return [
        CatalogEntry(
            id=r.id,
            game_name=r.game_name,
            game_slug=r.game_slug,
            publisher_name=r.publisher.name if r.publisher else "Unknown",
            version=r.version,
            status=r.status,
        )
        for r in rulesets
    ]


# ─── Get Catalog Detail ──────────────────────────────────────────────────────


@router.get("/{game_slug}", response_model=CatalogDetailEntry)
async def get_catalog_detail(
    game_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single catalog entry by game slug.

    Auth: None (public endpoint).
    Rate limit: None.
    Tier: Open to all.

    Args:
        game_slug: URL-safe game identifier (e.g., 'dnd-5e').

    Returns:
        Extended catalog entry with chunk count and namespace.

    Raises:
        HTTPException: 404 if game slug not found in catalog.
    """
    stmt = (
        select(OfficialRuleset)
        .options(selectinload(OfficialRuleset.publisher))
        .where(OfficialRuleset.game_slug == game_slug)
    )
    result = await db.execute(stmt)
    ruleset = result.scalar_one_or_none()

    if not ruleset:
        raise HTTPException(status_code=404, detail=f"Game '{game_slug}' not found in catalog.")

    return CatalogDetailEntry(
        id=ruleset.id,
        game_name=ruleset.game_name,
        game_slug=ruleset.game_slug,
        publisher_name=ruleset.publisher.name if ruleset.publisher else "Unknown",
        version=ruleset.version,
        status=ruleset.status,
        chunk_count=ruleset.chunk_count or 0,
        pinecone_namespace=ruleset.pinecone_namespace,
    )
