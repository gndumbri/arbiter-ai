"""open5e_ingester.py — Ingest open-license tabletop rules into pgvector.

This module fetches document metadata and section text from Open5e and indexes
eligible open-license content (Creative Commons, OGL, ORC) into `rule_chunks`.
It also creates/updates corresponding `official_rulesets` catalog rows.

Legal model:
- We only auto-index documents whose declared license matches an allowed list.
- Attribution/source metadata is persisted on every ruleset.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import OfficialRuleset, RuleChunk

logger = structlog.get_logger()

OPEN5E_DOCUMENTS_URL = "https://api.open5e.com/v1/documents/"
OPEN5E_SECTIONS_URL = "https://api.open5e.com/v1/sections/"

# Legacy SRD identity preserved for backward compatibility with existing rows.
SRD_SOURCE_DOCUMENT_SLUG = "wotc-srd"
SRD_SLUG = "srd-dnd-5e"
SRD_GAME_NAME = "Dungeons & Dragons 5th Edition (SRD)"

DEFAULT_ALLOWED_LICENSE_KEYWORDS = (
    "creative commons",
    "open gaming license",
    "orc",
)

# Maximum characters per chunk for embedding
_CHUNK_SIZE = 1500
# Overlap between chunks to preserve context
_CHUNK_OVERLAP = 200
# Embedding batch size (Bedrock Titan practical limit)
_EMBED_BATCH_SIZE = 25


@dataclass(frozen=True)
class Open5eDocument:
    """Normalized Open5e document metadata."""

    title: str
    slug: str
    source_url: str
    license_name: str
    organization: str
    version: str
    author: str
    copyright_notice: str


def _normalize_license(license_name: str) -> str:
    lower = license_name.lower()
    if "creative commons" in lower:
        return "CC-BY-4.0"
    if "open gaming license" in lower or "open game license" in lower or "ogl" in lower:
        return "OGL-1.0a"
    if "orc" in lower:
        return "ORC"
    return license_name.strip() or "OPEN_LICENSE"


def _is_allowed_license(license_name: str, allowed_keywords: Sequence[str]) -> bool:
    normalized = license_name.lower().replace("open game license", "open gaming license")
    return any(
        keyword.lower().replace("open game license", "open gaming license") in normalized
        for keyword in allowed_keywords
    )


def _ruleset_slug_for_document(document_slug: str) -> str:
    if document_slug == SRD_SOURCE_DOCUMENT_SLUG:
        return SRD_SLUG
    return f"open5e-{document_slug}"


def _ruleset_name_for_document(document: Open5eDocument) -> str:
    if document.slug == SRD_SOURCE_DOCUMENT_SLUG:
        return SRD_GAME_NAME
    return document.title


def _build_attribution(document: Open5eDocument) -> str:
    parts = [
        f"Source: {document.title}",
        f"License: {document.license_name}",
    ]
    if document.author:
        parts.append(f"Author(s): {document.author}")
    if document.copyright_notice:
        parts.append(f"Copyright notice: {document.copyright_notice}")
    if document.source_url:
        parts.append(f"Reference URL: {document.source_url}")
    return " | ".join(parts)


def _chunk_text(text: str, section_name: str) -> list[dict]:
    """Split text into overlapping chunks with deterministic IDs."""
    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + _CHUNK_SIZE
        chunk_text = text[start:end]
        chunk_id = hashlib.md5(
            f"{section_name}:{idx}:{chunk_text[:100]}".encode()
        ).hexdigest()

        chunks.append({
            "text": chunk_text,
            "section": section_name,
            "chunk_index": idx,
            "chunk_id": f"open5e_{chunk_id}",
        })
        start = end - _CHUNK_OVERLAP
        idx += 1

    return chunks


async def _fetch_documents() -> list[Open5eDocument]:
    """Fetch all document metadata from Open5e v1 API."""
    docs: list[Open5eDocument] = []
    url = f"{OPEN5E_DOCUMENTS_URL}?limit=200"

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError as exc:
                logger.warning("open5e_documents_fetch_error", error=str(exc), url=url)
                break

            for item in payload.get("results", []):
                title = str(item.get("title") or "").strip()
                slug = str(item.get("slug") or "").strip()
                if not title or not slug:
                    continue
                docs.append(Open5eDocument(
                    title=title,
                    slug=slug,
                    source_url=str(item.get("url") or "").strip(),
                    license_name=str(item.get("license") or "").strip(),
                    organization=str(item.get("organization") or "").strip(),
                    version=str(item.get("version") or "1.0").strip(),
                    author=str(item.get("author") or "").strip(),
                    copyright_notice=str(item.get("copyright") or "").strip(),
                ))
            url = payload.get("next")

    logger.info("open5e_documents_fetched", count=len(docs))
    return docs


async def _fetch_sections(document_slug: str) -> list[dict]:
    """Fetch all sections for a specific Open5e document slug."""
    sections = []
    url = f"{OPEN5E_SECTIONS_URL}?limit=500&document__slug={document_slug}"

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError as exc:
                logger.warning(
                    "open5e_sections_fetch_error",
                    error=str(exc),
                    document_slug=document_slug,
                    url=url,
                )
                break

            for section in payload.get("results", []):
                name = str(section.get("name") or "").strip()
                desc = str(section.get("desc") or "").strip()
                if name and desc:
                    sections.append({"name": name, "desc": desc})
            url = payload.get("next")

    logger.info(
        "open5e_sections_fetched",
        document_slug=document_slug,
        count=len(sections),
    )
    return sections


async def sync_open_licensed_documents(
    db: AsyncSession,
    publisher_id: uuid.UUID,
    *,
    max_documents: int | None = None,
    allowed_license_keywords: Sequence[str] = DEFAULT_ALLOWED_LICENSE_KEYWORDS,
    document_slugs: Iterable[str] | None = None,
    force_reindex: bool = False,
) -> dict[str, int]:
    """Fetch open-license Open5e documents and index them into rule_chunks.

    Returns counters so callers can log/report ingestion outcomes.
    """
    stats = {
        "documents_seen": 0,
        "documents_selected": 0,
        "rulesets_created": 0,
        "rulesets_updated": 0,
        "rulesets_indexed": 0,
        "chunks_indexed": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    documents = await _fetch_documents()
    stats["documents_seen"] = len(documents)

    selected_slugs = {slug for slug in (document_slugs or []) if slug}
    selected_docs = []
    for doc in documents:
        if selected_slugs and doc.slug not in selected_slugs:
            continue
        if not _is_allowed_license(doc.license_name, allowed_license_keywords):
            continue
        selected_docs.append(doc)

    if max_documents is not None and max_documents > 0:
        selected_docs = selected_docs[:max_documents]

    stats["documents_selected"] = len(selected_docs)
    if not selected_docs:
        logger.info("open5e_no_documents_selected")
        return stats

    from app.core.registry import get_provider_registry

    registry = get_provider_registry()
    embedder = registry.get_embedder()

    for document in selected_docs:
        try:
            sections = await _fetch_sections(document.slug)
            if not sections:
                continue

            all_chunks = []
            for section in sections:
                all_chunks.extend(_chunk_text(section["desc"], section["name"]))

            if not all_chunks:
                continue

            ruleset_slug = _ruleset_slug_for_document(document.slug)
            existing = await db.execute(
                select(OfficialRuleset).where(OfficialRuleset.game_slug == ruleset_slug)
            )
            ruleset = existing.scalar_one_or_none()

            if (
                ruleset is not None
                and not force_reindex
                and (ruleset.version == document.version)
                and (ruleset.chunk_count or 0) > 0
                and ruleset.status == "READY"
            ):
                stats["skipped_existing"] += 1
                continue

            if ruleset is None:
                ruleset = OfficialRuleset(
                    publisher_id=publisher_id,
                    game_name=_ruleset_name_for_document(document),
                    game_slug=ruleset_slug,
                    publisher_display_name=document.organization or "Open5e",
                    status="PROCESSING",
                    license_type=_normalize_license(document.license_name),
                    is_crawlable=True,
                    source_url=document.source_url or OPEN5E_DOCUMENTS_URL,
                    attribution_text=_build_attribution(document),
                    pinecone_namespace="",
                    version=document.version or "1.0",
                    chunk_count=0,
                    source_type="OPEN_LICENSE",
                    source_priority=100,
                )
                db.add(ruleset)
                await db.flush()
                stats["rulesets_created"] += 1
            else:
                ruleset.game_name = _ruleset_name_for_document(document)
                ruleset.publisher_display_name = document.organization or "Open5e"
                ruleset.status = "PROCESSING"
                ruleset.license_type = _normalize_license(document.license_name)
                ruleset.is_crawlable = True
                ruleset.source_url = document.source_url or OPEN5E_DOCUMENTS_URL
                ruleset.attribution_text = _build_attribution(document)
                ruleset.version = document.version or ruleset.version
                ruleset.source_type = "OPEN_LICENSE"
                ruleset.source_priority = 100
                stats["rulesets_updated"] += 1

            # Rebuild chunks to keep the index aligned with latest source version.
            await db.execute(delete(RuleChunk).where(RuleChunk.ruleset_id == ruleset.id))

            chunk_count = 0
            for i in range(0, len(all_chunks), _EMBED_BATCH_SIZE):
                batch = all_chunks[i : i + _EMBED_BATCH_SIZE]
                texts = [chunk["text"] for chunk in batch]
                result = await embedder.embed_texts(texts)

                for offset, (chunk, vector) in enumerate(
                    zip(batch, result.vectors, strict=False)
                ):
                    db.add(RuleChunk(
                        ruleset_id=ruleset.id,
                        chunk_index=i + offset,
                        chunk_text=chunk["text"],
                        section_header=chunk["section"],
                        embedding=vector,
                    ))
                    chunk_count += 1

            ruleset.status = "READY"
            ruleset.chunk_count = chunk_count
            await db.commit()

            stats["rulesets_indexed"] += 1
            stats["chunks_indexed"] += chunk_count
            logger.info(
                "open5e_document_indexed",
                slug=document.slug,
                ruleset_slug=ruleset_slug,
                chunks=chunk_count,
            )
        except Exception as exc:
            stats["failed"] += 1
            await db.rollback()
            logger.warning(
                "open5e_document_sync_failed",
                slug=document.slug,
                error=str(exc),
            )

    logger.info("open5e_sync_complete", **stats)
    return stats


async def sync_srd(db: AsyncSession, publisher_id: uuid.UUID) -> int:
    """Backward-compatible wrapper that syncs only the legacy SRD document."""
    stats = await sync_open_licensed_documents(
        db,
        publisher_id,
        document_slugs=[SRD_SOURCE_DOCUMENT_SLUG],
        max_documents=1,
        allowed_license_keywords=DEFAULT_ALLOWED_LICENSE_KEYWORDS,
        force_reindex=False,
    )
    return stats["chunks_indexed"]
