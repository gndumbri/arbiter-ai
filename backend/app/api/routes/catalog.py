"""catalog.py — Public game catalog browsing endpoints.

Lists official game rulesets from verified publishers. This is a
read-only public API — no auth required.

Endpoints:
    GET /api/v1/catalog/           → List all published rulesets (with optional search)
    GET /api/v1/catalog/{slug}     → Get a single ruleset by game slug

Called by: Frontend catalog page (CatalogPage component), RulesetUploadDialog wizard.
Depends on: deps.py (get_db), tables.py (OfficialRuleset, Publisher)

Architecture note for AI agents:
    The catalog lists OfficialRuleset entries that have been pushed by
    publishers via POST /publishers/{id}/games, seeded by seed_catalog.py,
    or ingested from external sources (BGG, Open5e).
    The frontend RulesetUploadDialog uses the ?search= param to find games.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.tables import OfficialRuleset, Publisher

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])

# Statuses that should be visible in the Armory/catalog UI.
# - READY/INDEXED/COMPLETE/PUBLISHED: immediate "chat now" experiences.
# - UPLOAD_REQUIRED: metadata-only entries that still power discovery.
CATALOG_VISIBLE_STATUSES = (
    "READY",
    "INDEXED",
    "COMPLETE",
    "PUBLISHED",
    "UPLOAD_REQUIRED",
)


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
    license_type: str | None = None
    attribution_text: str | None = None


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
    license_type: str | None = None
    attribution_text: str | None = None


# ─── List Catalog ─────────────────────────────────────────────────────────────


@router.get("/", response_model=list[CatalogEntry])
async def list_verified_games(
    search: str | None = Query(
        None,
        description="Search games by name or publisher (case-insensitive ILIKE).",
    ),
    db: AsyncSession = Depends(get_db),
):
    """List all official rulesets in the catalog (with optional search).

    Auth: None (public endpoint).
    Rate limit: None.
    Tier: Open to all.

    Args:
        search: Optional text filter. Matches game_name or publisher_display_name
                using case-insensitive ILIKE.

    Returns:
        List of catalog entries with game name, slug, publisher, version, license.
    """
    stmt = (
        select(OfficialRuleset)
        .options(selectinload(OfficialRuleset.publisher))
        .where(
            OfficialRuleset.status.in_(CATALOG_VISIBLE_STATUSES),
            OfficialRuleset.publisher.has(Publisher.verified.is_(True)),
        )
    )

    # WHY: The search param powers the RulesetUploadDialog wizard (Step 1).
    # Users type a game name and see matching results in real-time.
    if search:
        # WHY: Escape SQL LIKE wildcard characters to prevent pattern injection.
        # Without escaping, a search for "100%" would match everything.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like_term = f"%{escaped}%"
        stmt = stmt.where(
            OfficialRuleset.game_name.ilike(like_term, escape="\\")
            | OfficialRuleset.publisher_display_name.ilike(like_term, escape="\\")
            | OfficialRuleset.publisher.has(Publisher.name.ilike(like_term, escape="\\"))
        )

    # Put chat-ready entries first, then stable alphabetical ordering.
    ready_first = case(
        (
            OfficialRuleset.status.in_(("READY", "INDEXED", "COMPLETE", "PUBLISHED")),
            0,
        ),
        else_=1,
    )
    stmt = stmt.order_by(ready_first, OfficialRuleset.game_name.asc())

    result = await db.execute(stmt)
    rulesets = result.scalars().all()

    return [
        CatalogEntry(
            id=r.id,
            game_name=r.game_name,
            game_slug=r.game_slug,
            publisher_name=r.publisher_display_name or (r.publisher.name if r.publisher else "Unknown"),
            version=r.version,
            status=r.status,
            license_type=r.license_type,
            attribution_text=r.attribution_text,
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
        .where(
            OfficialRuleset.game_slug == game_slug,
            OfficialRuleset.status.in_(CATALOG_VISIBLE_STATUSES),
            OfficialRuleset.publisher.has(Publisher.verified.is_(True)),
        )
    )
    result = await db.execute(stmt)
    ruleset = result.scalar_one_or_none()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Game not found in catalog.")

    return CatalogDetailEntry(
        id=ruleset.id,
        game_name=ruleset.game_name,
        game_slug=ruleset.game_slug,
        publisher_name=ruleset.publisher_display_name or (ruleset.publisher.name if ruleset.publisher else "Unknown"),
        version=ruleset.version,
        status=ruleset.status,
        chunk_count=ruleset.chunk_count or 0,
        pinecone_namespace=ruleset.pinecone_namespace,
        license_type=ruleset.license_type,
        attribution_text=ruleset.attribution_text,
    )
