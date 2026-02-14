"""Ingestion pipeline — 3-layer defense-in-depth for PDF processing.

Uses provider protocols for all external dependencies (LLM, embeddings,
vector store, document parser). Swap any provider without changing this code.

Pipeline steps:
    Layer 1: Validation (magic bytes, size, hash blocklist)
    Layer 2: Classification (LLM-based rulebook detection)
    Layer 3: Parse → Chunk → Embed → Index → Cleanup
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from app.core.chunking import Chunk, chunk_document
from app.core.protocols import (
    DocumentParserProvider,
    EmbeddingProvider,
    LLMProvider,
    Message,
    VectorRecord,
    VectorStoreProvider,
)

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES = b"%PDF-"
MAX_FILE_SIZE_MB = 50
MAX_PAGE_COUNT = 500


class IngestionError(Exception):
    """Base error for ingestion pipeline failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class IngestionPipeline:
    """Orchestrates the 3-layer ingestion pipeline.

    All external dependencies injected via protocols — swap providers
    by changing config, not code.
    """

    def __init__(
        self,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        vector_store: VectorStoreProvider,
        parser: DocumentParserProvider,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._vector_store = vector_store
        self._parser = parser

    async def process(
        self,
        file_path: str,
        *,
        ruleset_id: str,
        user_id: str,
        session_id: str,
        game_name: str,
        source_type: str = "BASE",
        source_priority: int = 0,
        namespace: str | None = None,
        blocklist_hashes: set[str] | None = None,
    ) -> IngestionResult:
        """Run the full ingestion pipeline.

        Args:
            file_path: Path to the uploaded PDF
            ruleset_id: UUID of the ruleset_metadata row
            user_id: UUID of the uploading user
            session_id: UUID of the active session
            game_name: Name of the game
            source_type: BASE, EXPANSION, or ERRATA
            source_priority: 0=Base, 10=Expansion, 100=Errata
            namespace: Pinecone namespace (defaults to user_{user_id})
            blocklist_hashes: Set of blocked file hashes

        Returns:
            IngestionResult with chunk count and status
        """
        target_namespace = namespace or f"user_{user_id}"
        path = Path(file_path)

        try:
            # ── Layer 1: Validation ──
            file_hash = await self._validate(path, blocklist_hashes or set())

            # ── Layer 2: Classification ──
            await self._classify_as_rulebook(path)

            # ── Layer 3: Parse → Chunk → Embed → Index ──
            parsed = await self._parser.parse(file_path)
            logger.info(
                "Parsed %d sections from %s",
                len(parsed.sections),
                path.name,
            )

            chunks = chunk_document(parsed)
            logger.info("Created %d chunks from %s", len(chunks), path.name)

            # Embed all chunks
            texts = [c.text for c in chunks]
            embedding_result = await self._embedder.embed_texts(texts)

            # Build vector records
            vectors = self._build_vectors(
                chunks=chunks,
                embeddings=embedding_result.vectors,
                ruleset_id=ruleset_id,
                session_id=session_id,
                game_name=game_name,
                source_type=source_type,
                source_priority=source_priority,
                is_official=namespace is not None and namespace.startswith("official_"),
            )

            # Upsert to vector store
            upserted = await self._vector_store.upsert(
                vectors, namespace=target_namespace
            )

            # Verify count
            stats = await self._vector_store.namespace_stats(target_namespace)
            logger.info(
                "Upserted %d vectors to '%s' (total: %d)",
                upserted,
                target_namespace,
                stats.get("vector_count", 0),
            )

            return IngestionResult(
                status="INDEXED",
                chunk_count=len(chunks),
                file_hash=file_hash,
                namespace=target_namespace,
            )

        except IngestionError:
            raise
        except Exception as exc:
            logger.exception("Ingestion failed for %s", path.name)
            raise IngestionError(
                code="PROCESSING_FAILED",
                message=f"Ingestion failed: {exc}",
            ) from exc
        finally:
            # ── Cleanup: HARD DELETE source PDF ──
            self._cleanup(path)

    # ── Layer 1: Validation ────────────────────────────────────────────────────

    async def _validate(
        self,
        path: Path,
        blocklist_hashes: set[str],
    ) -> str:
        """Validate file type, size, and hash."""
        if not path.exists():
            raise IngestionError("VALIDATION_ERROR", "File not found")

        # Magic bytes check
        with open(path, "rb") as f:
            header = f.read(5)
        if header != PDF_MAGIC_BYTES:
            raise IngestionError("VALIDATION_ERROR", "File is not a valid PDF")

        # Size check
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise IngestionError(
                "VALIDATION_ERROR",
                f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)",
            )

        # Hash check
        file_hash = self._compute_hash(path)
        if file_hash in blocklist_hashes:
            raise IngestionError("BLOCKED_FILE", "This file has been blocked")

        return file_hash

    # ── Layer 2: Classification ────────────────────────────────────────────────

    async def _classify_as_rulebook(self, path: Path) -> None:
        """Use LLM to verify the document is a game rulebook."""
        # Parse first 3 pages for quick classification
        quick_parse = await self._parser.parse(str(path), max_pages=3)
        sample_text = quick_parse.raw_text[:3000]

        if not sample_text.strip():
            raise IngestionError("NOT_A_RULEBOOK", "Document appears to be empty")

        response = await self._llm.complete(
            messages=[
                Message(
                    role="system",
                    content=(
                        "You are a document classifier. Determine if the provided "
                        "text is from a board game, card game, or tabletop game "
                        "rulebook. Look for terms like 'Setup', 'Turn Order', "
                        "'Victory Points', 'Components', 'Players', 'Dice', 'Cards', "
                        "'Game Board'. Answer ONLY with 'YES' or 'NO' followed by "
                        "a one-sentence reason."
                    ),
                ),
                Message(
                    role="user",
                    content=f"Is this a game rulebook?\n\n{sample_text}",
                ),
            ],
            model=None,  # Uses fast model configured in provider
            temperature=0.0,
            max_tokens=100,
        )

        answer = response.content.strip().upper()
        if not answer.startswith("YES"):
            raise IngestionError(
                "NOT_A_RULEBOOK",
                "Upload rejected. This does not appear to be a valid game rulebook.",
            )

        logger.info("Document classified as rulebook")

    # ── Vector Record Builder ──────────────────────────────────────────────────

    def _build_vectors(
        self,
        *,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        ruleset_id: str,
        session_id: str,
        game_name: str,
        source_type: str,
        source_priority: int,
        is_official: bool,
    ) -> list[VectorRecord]:
        """Build VectorRecord objects with full metadata."""
        vectors = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            vector_id = f"{ruleset_id}_{chunk.chunk_index}"
            vectors.append(
                VectorRecord(
                    id=vector_id,
                    vector=embedding,
                    metadata={
                        "text": chunk.text[:1000],  # Pinecone metadata limit
                        "page_number": chunk.page_number,
                        "section_header": chunk.header_path,
                        "source_type": source_type,
                        "source_priority": source_priority,
                        "is_official": is_official,
                        "ruleset_id": ruleset_id,
                        "session_id": session_id,
                        "game_name": game_name,
                        "section_type": chunk.section_type,
                    },
                )
            )
        return vectors

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(path: Path) -> str:
        """SHA-256 hash of file contents."""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha.update(block)
        return sha.hexdigest()

    @staticmethod
    def _cleanup(path: Path) -> None:
        """Hard delete the source file."""
        try:
            if path.exists():
                # Overwrite before delete for security
                size = path.stat().st_size
                with open(path, "wb") as f:
                    f.write(os.urandom(min(size, 4096)))
                path.unlink()
                logger.info("Cleaned up source file: %s", path.name)
        except OSError as exc:
            logger.warning("Failed to cleanup %s: %s", path.name, exc)


class IngestionResult:
    """Result of a completed ingestion."""

    def __init__(
        self,
        status: str,
        chunk_count: int,
        file_hash: str,
        namespace: str,
    ) -> None:
        self.status = status
        self.chunk_count = chunk_count
        self.file_hash = file_hash
        self.namespace = namespace
