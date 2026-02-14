"""Docling document parser provider — PDF layout-aware parsing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.protocols import ParsedDocument, ParsedSection
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class DoclingParserProvider:
    """Docling-based PDF parser with layout detection and table extraction.

    Handles multi-column layouts, tables, sidebars, and hierarchical headers
    that are critical for board game rulebooks.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def parse(
        self,
        file_path: str,
        *,
        max_pages: int | None = None,
    ) -> ParsedDocument:
        """Parse a PDF file into structured sections.

        Uses Docling for deep layout analysis. Falls back to PyMuPDF
        for basic extraction if Docling fails.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            return await self._parse_with_docling(path, max_pages)
        except Exception as exc:
            logger.warning(
                "Docling parsing failed, falling back to basic extraction: %s",
                str(exc),
            )
            return await self._parse_fallback(path, max_pages)

    async def _parse_with_docling(
        self,
        path: Path,
        max_pages: int | None,
    ) -> ParsedDocument:
        """Parse using Docling for full layout analysis."""
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document

        sections: list[ParsedSection] = []
        current_header = ""

        for element in doc.iterate_items():
            item = element[1] if isinstance(element, tuple) else element

            # Extract text content
            text = ""
            if hasattr(item, "text"):
                text = item.text
            elif hasattr(item, "export_to_markdown"):
                text = item.export_to_markdown()

            if not text or not text.strip():
                continue

            # Determine section type
            section_type = "text"
            label = getattr(item, "label", "")

            if "heading" in str(label).lower() or "title" in str(label).lower():
                current_header = text.strip()
                continue
            elif "table" in str(label).lower():
                section_type = "table"
            elif "list" in str(label).lower():
                section_type = "list"

            # Extract page info
            page_number = None
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                page_number = getattr(prov, "page_no", None)

            sections.append(
                ParsedSection(
                    header_path=current_header,
                    content=text.strip(),
                    page_number=page_number,
                    section_type=section_type,
                )
            )

        # Metadata
        metadata: dict[str, Any] = {}
        if hasattr(doc, "pages"):
            metadata["page_count"] = len(doc.pages)
        if hasattr(doc, "name"):
            metadata["title"] = doc.name

        raw_text = "\n\n".join(s.content for s in sections)

        return ParsedDocument(
            sections=sections,
            metadata=metadata,
            raw_text=raw_text,
        )

    async def _parse_fallback(
        self,
        path: Path,
        max_pages: int | None,
    ) -> ParsedDocument:
        """Basic fallback parser using PyMuPDF."""
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        sections: list[ParsedSection] = []
        all_text_parts: list[str] = []

        page_limit = max_pages or len(doc)
        for page_num in range(min(page_limit, len(doc))):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                sections.append(
                    ParsedSection(
                        header_path=f"Page {page_num + 1}",
                        content=text.strip(),
                        page_number=page_num + 1,
                        section_type="text",
                    )
                )
                all_text_parts.append(text.strip())

        doc.close()

        return ParsedDocument(
            sections=sections,
            metadata={"page_count": len(doc), "parser": "fallback_pymupdf"},
            raw_text="\n\n".join(all_text_parts),
        )


# Self-register on import
register_provider("parser", "docling", DoclingParserProvider)
