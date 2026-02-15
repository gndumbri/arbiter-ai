"""open5e_ingester.py — Fetch and vectorize D&D 5e SRD sections.

LEGAL CONTEXT: The D&D 5e System Reference Document (SRD 5.1) is
released under the Creative Commons Attribution 4.0 International
License (CC-BY-4.0). We are legally permitted to host, index, and
serve this content with proper attribution.

Source: Open5e API (https://api.open5e.com/v1/sections/)
License: CC-BY-4.0
Attribution: "This work includes material taken from the System
Reference Document 5.1 ('SRD 5.1') by Wizards of the Coast LLC..."

Pipeline:
    1. Fetch SRD sections from Open5e API
    2. Chunk text content into manageable pieces
    3. Generate embeddings via registry.get_embedder()
    4. Store as RuleChunk rows with pgvector embeddings (replaces Pinecone)
    5. Create/update OfficialRuleset with status=READY
"""

from __future__ import annotations

import hashlib
import uuid

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import OfficialRuleset, RuleChunk

logger = structlog.get_logger()

OPEN5E_SECTIONS_URL = "https://api.open5e.com/v1/sections/"
SRD_NAMESPACE = "srd_dnd_5e"
SRD_SLUG = "srd-dnd-5e"
SRD_GAME_NAME = "Dungeons & Dragons 5th Edition (SRD)"
SRD_ATTRIBUTION = (
    "This work includes material taken from the System Reference Document 5.1 "
    "('SRD 5.1') by Wizards of the Coast LLC, available at "
    "https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 "
    "is licensed under the Creative Commons Attribution 4.0 International License "
    "(CC-BY-4.0), available at https://creativecommons.org/licenses/by/4.0/."
)

# Maximum characters per chunk for embedding
_CHUNK_SIZE = 1500
# Overlap between chunks to preserve context
_CHUNK_OVERLAP = 200
# Embedding batch size (Bedrock Titan limit)
_EMBED_BATCH_SIZE = 25


def _chunk_text(text: str, section_name: str) -> list[dict]:
    """Split text into overlapping chunks with metadata.

    WHY: Embedding models have token limits. We split into ~1500-char
    chunks with 200-char overlap to maintain context across boundaries.

    Returns a list of dicts: {text, section, chunk_index, chunk_id}
    """
    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + _CHUNK_SIZE
        chunk_text = text[start:end]

        # Generate a deterministic ID from content for idempotent upserts
        chunk_id = hashlib.md5(
            f"{section_name}:{idx}:{chunk_text[:100]}".encode()
        ).hexdigest()

        chunks.append({
            "text": chunk_text,
            "section": section_name,
            "chunk_index": idx,
            "chunk_id": f"srd_{chunk_id}",
        })

        start = end - _CHUNK_OVERLAP
        idx += 1

    return chunks


async def _fetch_sections() -> list[dict]:
    """Fetch all SRD sections from Open5e API.

    Returns a list of section dicts with 'name' and 'desc' fields.
    Paginates through all results automatically.
    """
    sections = []
    url = f"{OPEN5E_SECTIONS_URL}?limit=500&document__slug=wotc-srd"

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                for section in data.get("results", []):
                    name = section.get("name", "")
                    desc = section.get("desc", "")
                    if name and desc:
                        sections.append({
                            "name": name,
                            "desc": desc,
                            "slug": section.get("slug", name.lower()),
                        })

                url = data.get("next")
            except httpx.HTTPError as e:
                logger.warning("open5e_fetch_error", error=str(e), url=url)
                break

    logger.info("open5e_sections_fetched", count=len(sections))
    return sections


async def sync_srd(db: AsyncSession, publisher_id: uuid.UUID) -> int:
    """Fetch SRD sections, vectorize, and create a READY catalog entry.

    This function:
    1. Fetches D&D 5e SRD sections from Open5e
    2. Chunks text content
    3. Embeds and stores as RuleChunk rows with pgvector (replaces Pinecone)
    4. Creates/updates the SRD catalog entry

    Args:
        db: Active database session.
        publisher_id: UUID of the Community Catalog publisher.

    Returns:
        Number of chunks indexed (0 if vectorization failed/skipped).
    """
    sections = await _fetch_sections()
    if not sections:
        logger.warning("open5e_no_sections")
        return 0

    # 1. Chunk all sections
    all_chunks = []
    for section in sections:
        chunks = _chunk_text(section["desc"], section["name"])
        all_chunks.extend(chunks)

    logger.info("open5e_chunks_created", total_chunks=len(all_chunks))

    # 2. Create/find the SRD catalog entry first (we need ruleset.id for chunks)
    existing = await db.execute(
        select(OfficialRuleset).where(OfficialRuleset.game_slug == SRD_SLUG)
    )
    srd_entry = existing.scalar_one_or_none()

    if srd_entry:
        # Check if already has chunks — skip if so (idempotent)
        chunk_check = await db.execute(
            select(RuleChunk.id).where(RuleChunk.ruleset_id == srd_entry.id).limit(1)
        )
        if chunk_check.scalar_one_or_none():
            logger.info("open5e_srd_already_ingested", slug=SRD_SLUG)
            return 0
    else:
        srd_entry = OfficialRuleset(
            publisher_id=publisher_id,
            game_name=SRD_GAME_NAME,
            game_slug=SRD_SLUG,
            publisher_display_name="Wizards of the Coast (SRD)",
            status="PROCESSING",
            license_type="CC-BY-4.0",
            is_crawlable=True,
            source_url=OPEN5E_SECTIONS_URL,
            attribution_text=SRD_ATTRIBUTION,
            pinecone_namespace="",
            version="5.1 SRD",
            chunk_count=0,
        )
        db.add(srd_entry)
        await db.flush()

    # 3. Embed and store as RuleChunk rows (pgvector, replaces Pinecone)
    chunk_count = 0
    try:
        from app.core.registry import get_provider_registry

        registry = get_provider_registry()
        embedder = registry.get_embedder()

        # Embed in batches
        for i in range(0, len(all_chunks), _EMBED_BATCH_SIZE):
            batch = all_chunks[i : i + _EMBED_BATCH_SIZE]
            texts = [c["text"] for c in batch]

            result = await embedder.embed_texts(texts)

            for chunk, vector in zip(batch, result.vectors, strict=False):
                db.add(RuleChunk(
                    ruleset_id=srd_entry.id,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["text"],
                    section_header=chunk["section"],
                    embedding=vector,
                ))
                chunk_count += 1

        # Update ruleset to READY with chunk count
        srd_entry.status = "READY"
        srd_entry.chunk_count = chunk_count
        logger.info("open5e_vectorized", chunks=chunk_count)

    except Exception as e:
        # Graceful fallback: if embedder isn't configured, we still create
        # the catalog entry but leave it as PROCESSING (not READY).
        logger.warning(
            "open5e_vectorization_skipped",
            error=str(e),
            reason="Embedding provider not configured. "
            "SRD entry created but requires manual embedding.",
        )

    await db.flush()
    return chunk_count
