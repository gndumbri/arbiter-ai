"""Context-aware chunking for board game rulebooks.

Implements recursive semantic splitting with:
- Header prepending for retrieval context
- Table preservation (never splits a table row)
- Configurable chunk sizes with overlap
- Section hierarchy from parsed documents
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.core.protocols import ParsedDocument, ParsedSection

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_TARGET_TOKENS = 400
DEFAULT_MIN_TOKENS = 200
DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 50

# Rough approximation: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    """A single chunk ready for embedding."""

    text: str
    header_path: str
    page_number: int | None = None
    section_type: str = "text"
    chunk_index: int = 0
    token_estimate: int = 0
    metadata: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Rough token count estimate."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def chunk_document(
    doc: ParsedDocument,
    *,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk a parsed document using recursive semantic splitting.

    Algorithm:
    1. Split on structural headers first (preserves section boundaries)
    2. Within sections: split on paragraph boundaries
    3. Merge chunks < min_tokens with neighbors
    4. Split chunks > max_tokens recursively at sentence boundaries
    5. Prepend section header path to each chunk for retrieval context
    """
    raw_chunks: list[Chunk] = []

    for section in doc.sections:
        section_chunks = _chunk_section(
            section,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
        )
        raw_chunks.extend(section_chunks)

    # Merge small chunks
    merged = _merge_small_chunks(raw_chunks, min_tokens=min_tokens)

    # Add overlap between adjacent chunks
    overlapped = _add_overlap(merged, overlap_tokens=overlap_tokens)

    # Prepend headers and assign indices
    final_chunks: list[Chunk] = []
    for i, chunk in enumerate(overlapped):
        # Prepend header path for retrieval context
        if chunk.header_path:
            chunk.text = f"{chunk.header_path}: {chunk.text}"

        chunk.chunk_index = i
        chunk.token_estimate = estimate_tokens(chunk.text)
        final_chunks.append(chunk)

    logger.info(
        "Chunked document into %d chunks (avg %d tokens)",
        len(final_chunks),
        sum(c.token_estimate for c in final_chunks) // max(len(final_chunks), 1),
    )
    return final_chunks


def _chunk_section(
    section: ParsedSection,
    *,
    target_tokens: int,
    max_tokens: int,
) -> list[Chunk]:
    """Split a single section into chunks."""
    # Tables are atomic — never split
    if section.section_type == "table":
        return [
            Chunk(
                text=section.content,
                header_path=section.header_path,
                page_number=section.page_number,
                section_type="table",
            )
        ]

    tokens = estimate_tokens(section.content)

    # Short enough — single chunk
    if tokens <= max_tokens:
        return [
            Chunk(
                text=section.content,
                header_path=section.header_path,
                page_number=section.page_number,
                section_type=section.section_type,
            )
        ]

    # Too long — split recursively
    return _recursive_split(
        section.content,
        header_path=section.header_path,
        page_number=section.page_number,
        section_type=section.section_type,
        target_tokens=target_tokens,
        max_tokens=max_tokens,
    )


def _recursive_split(
    text: str,
    *,
    header_path: str,
    page_number: int | None,
    section_type: str,
    target_tokens: int,
    max_tokens: int,
) -> list[Chunk]:
    """Recursively split text at paragraph → sentence boundaries."""
    tokens = estimate_tokens(text)

    if tokens <= max_tokens:
        return [
            Chunk(
                text=text.strip(),
                header_path=header_path,
                page_number=page_number,
                section_type=section_type,
            )
        ]

    # Try splitting at paragraph boundaries first
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) > 1:
        return _split_and_recurse(
            paragraphs,
            header_path=header_path,
            page_number=page_number,
            section_type=section_type,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
        )

    # Fall back to sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) > 1:
        return _split_and_recurse(
            sentences,
            header_path=header_path,
            page_number=page_number,
            section_type=section_type,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
        )

    # Last resort: hard split at token boundary
    chars = target_tokens * CHARS_PER_TOKEN
    chunks = []
    for i in range(0, len(text), chars):
        chunk_text = text[i : i + chars].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    text=chunk_text,
                    header_path=header_path,
                    page_number=page_number,
                    section_type=section_type,
                )
            )
    return chunks


def _split_and_recurse(
    parts: list[str],
    *,
    header_path: str,
    page_number: int | None,
    section_type: str,
    target_tokens: int,
    max_tokens: int,
) -> list[Chunk]:
    """Group parts into target-sized chunks, recursing if any exceed max."""
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        part_tokens = estimate_tokens(part)

        if current_tokens + part_tokens > max_tokens and current_parts:
            # Flush current accumulation
            combined = "\n\n".join(current_parts)
            chunks.append(
                Chunk(
                    text=combined,
                    header_path=header_path,
                    page_number=page_number,
                    section_type=section_type,
                )
            )
            current_parts = []
            current_tokens = 0

        current_parts.append(part)
        current_tokens += part_tokens

    # Flush remaining
    if current_parts:
        combined = "\n\n".join(current_parts)
        # Recurse if still too large
        if estimate_tokens(combined) > max_tokens:
            chunks.extend(
                _recursive_split(
                    combined,
                    header_path=header_path,
                    page_number=page_number,
                    section_type=section_type,
                    target_tokens=target_tokens,
                    max_tokens=max_tokens,
                )
            )
        else:
            chunks.append(
                Chunk(
                    text=combined,
                    header_path=header_path,
                    page_number=page_number,
                    section_type=section_type,
                )
            )

    return chunks


def _merge_small_chunks(
    chunks: list[Chunk],
    *,
    min_tokens: int,
) -> list[Chunk]:
    """Merge chunks smaller than min_tokens with their neighbor."""
    if not chunks:
        return []

    merged: list[Chunk] = [chunks[0]]

    for chunk in chunks[1:]:
        prev = merged[-1]
        prev_tokens = estimate_tokens(prev.text)

        if prev_tokens < min_tokens:
            # Merge with previous
            prev.text = f"{prev.text}\n\n{chunk.text}"
            # Keep the earlier page number
            if chunk.page_number and not prev.page_number:
                prev.page_number = chunk.page_number
        else:
            merged.append(chunk)

    return merged


def _add_overlap(
    chunks: list[Chunk],
    *,
    overlap_tokens: int,
) -> list[Chunk]:
    """Add overlap from previous chunk to the beginning of each chunk."""
    if len(chunks) <= 1 or overlap_tokens <= 0:
        return chunks

    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    for i in range(1, len(chunks)):
        prev_text = chunks[i - 1].text
        if len(prev_text) > overlap_chars:
            # Take from the end of previous chunk
            overlap = prev_text[-overlap_chars:]
            # Try to start at a word boundary
            space_idx = overlap.find(" ")
            if space_idx > 0:
                overlap = overlap[space_idx + 1 :]
            chunks[i].text = f"...{overlap} {chunks[i].text}"

    return chunks
