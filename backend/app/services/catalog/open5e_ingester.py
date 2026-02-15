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
    4. Upsert vectors into Pinecone under namespace "srd_dnd_5e"
    5. Create/update OfficialRuleset with status=READY
"""

from __future__ import annotations

import hashlib
import uuid

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import OfficialRuleset

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
# Embedding batch size
_EMBED_BATCH_SIZE = 50


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
    3. Attempts to embed and vectorize into Pinecone (graceful fallback)
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

    # 2. Try to vectorize (graceful fallback if Pinecone not configured)
    chunk_count = 0
    pinecone_namespace = ""
    status = "UPLOAD_REQUIRED"  # Default: fallback if vectorization fails

    try:
        from app.core.registry import get_provider_registry

        registry = get_provider_registry()
        embedder = registry.get_embedder()
        vector_store = registry.get_vector_store()

        # Import VectorRecord for building upsert payloads
        from app.core.protocols import VectorRecord

        # Embed in batches
        all_vectors: list[VectorRecord] = []
        for i in range(0, len(all_chunks), _EMBED_BATCH_SIZE):
            batch = all_chunks[i : i + _EMBED_BATCH_SIZE]
            texts = [c["text"] for c in batch]

            result = await embedder.embed_texts(texts)

            for chunk, embedding in zip(batch, result.vectors):
                record = VectorRecord(
                    id=chunk["chunk_id"],
                    vector=embedding,
                    metadata={
                        "text": chunk["text"][:1000],  # Pinecone metadata limit
                        "section": chunk["section"],
                        "chunk_index": chunk["chunk_index"],
                        "game_name": SRD_GAME_NAME,
                        "source_type": "OFFICIAL_SRD",
                        "license": "CC-BY-4.0",
                    },
                )
                all_vectors.append(record)

        # Upsert all vectors to Pinecone
        if all_vectors:
            chunk_count = await vector_store.upsert(
                all_vectors, namespace=SRD_NAMESPACE
            )
            pinecone_namespace = SRD_NAMESPACE
            status = "READY"
            logger.info(
                "open5e_vectorized",
                chunks=chunk_count,
                namespace=SRD_NAMESPACE,
            )

    except Exception as e:
        # Graceful fallback: if embedder or Pinecone isn't configured,
        # we still create the catalog entry but with UPLOAD_REQUIRED status.
        logger.warning(
            "open5e_vectorization_skipped",
            error=str(e),
            reason="Pinecone or embedding provider not configured. "
            "SRD will be listed but users must upload their own copy.",
        )

    # 3. Upsert the SRD catalog entry
    existing = await db.execute(
        select(OfficialRuleset).where(OfficialRuleset.game_slug == SRD_SLUG)
    )
    srd_entry = existing.scalar_one_or_none()

    if srd_entry:
        # Update existing entry
        srd_entry.status = status
        srd_entry.chunk_count = chunk_count
        srd_entry.pinecone_namespace = pinecone_namespace or srd_entry.pinecone_namespace
        srd_entry.license_type = "CC-BY-4.0"
        srd_entry.is_crawlable = True
        srd_entry.source_url = OPEN5E_SECTIONS_URL
        srd_entry.attribution_text = SRD_ATTRIBUTION
        logger.info("open5e_srd_updated", slug=SRD_SLUG, status=status)
    else:
        # Create new entry
        srd_entry = OfficialRuleset(
            publisher_id=publisher_id,
            game_name=SRD_GAME_NAME,
            game_slug=SRD_SLUG,
            publisher_display_name="Wizards of the Coast (SRD)",
            status=status,
            license_type="CC-BY-4.0",
            is_crawlable=True,
            source_url=OPEN5E_SECTIONS_URL,
            attribution_text=SRD_ATTRIBUTION,
            pinecone_namespace=pinecone_namespace,
            version="5.1 SRD",
            chunk_count=chunk_count,
        )
        db.add(srd_entry)
        logger.info("open5e_srd_created", slug=SRD_SLUG, status=status)

    await db.flush()
    return chunk_count
