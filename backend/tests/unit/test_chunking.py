"""Tests for context-aware chunking algorithm."""

from __future__ import annotations

from app.core.chunking import chunk_document, estimate_tokens
from app.core.protocols import ParsedDocument, ParsedSection


def test_estimate_tokens() -> None:
    """Token estimation should be roughly len/4."""
    assert estimate_tokens("hello world") == 2
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("") == 1  # Minimum 1


def test_single_short_section() -> None:
    """A short section should produce exactly one chunk."""
    doc = ParsedDocument(
        sections=[
            ParsedSection(
                header_path="Setup",
                content="Place the board in the center of the table.",
                page_number=1,
            )
        ],
        raw_text="Place the board in the center of the table.",
    )
    chunks = chunk_document(doc)
    assert len(chunks) >= 1
    assert "Setup" in chunks[0].text


def test_header_prepending() -> None:
    """Chunks should have their header path prepended."""
    doc = ParsedDocument(
        sections=[
            ParsedSection(
                header_path="Combat > Dice Roll",
                content="Roll 2d6 and add modifier.",
                page_number=5,
            )
        ],
    )
    chunks = chunk_document(doc)
    assert chunks[0].text.startswith("Combat > Dice Roll:")


def test_table_never_split() -> None:
    """Tables should be kept as atomic chunks, never split."""
    big_table = "| Col1 | Col2 |\n" + "| data | data |\n" * 200
    doc = ParsedDocument(
        sections=[
            ParsedSection(
                header_path="Components",
                content=big_table,
                page_number=2,
                section_type="table",
            )
        ],
    )
    chunks = chunk_document(doc)
    # Table should be one chunk regardless of size
    table_chunks = [c for c in chunks if c.section_type == "table"]
    assert len(table_chunks) == 1


def test_long_section_gets_split() -> None:
    """A very long section should be split into multiple chunks."""
    long_text = "This is a sentence about game rules. " * 500
    doc = ParsedDocument(
        sections=[
            ParsedSection(
                header_path="Rules",
                content=long_text,
                page_number=1,
            )
        ],
    )
    chunks = chunk_document(doc)
    assert len(chunks) > 1


def test_chunk_indices_are_sequential() -> None:
    """Chunk indices should be 0, 1, 2, ..."""
    doc = ParsedDocument(
        sections=[
            ParsedSection(header_path="A", content="Short text A.", page_number=1),
            ParsedSection(header_path="B", content="Short text B.", page_number=2),
            ParsedSection(header_path="C", content="Short text C.", page_number=3),
        ],
    )
    chunks = chunk_document(doc)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
