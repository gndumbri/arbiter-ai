"""mock_embedding.py — Mock embedding provider for testing without API calls.

Implements the EmbeddingProvider protocol with deterministic pseudo-random
vectors. Same text always produces the same vector, enabling reproducible
tests and demos without any embedding API keys.

Called by: Ingestion pipeline (via registry) when EMBEDDING_PROVIDER=mock
Depends on: protocols.py (EmbeddingProvider), factory.py (vector generation)
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.protocols import EmbeddingResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)

# WHY: 1024 dimensions matches the Titan Embed v2 model used in production.
# Keeping mock vectors the same size avoids dimension mismatch errors
# if any code validates vector length.
DEFAULT_DIMENSIONS = 1024


class MockEmbeddingProvider:
    """Fake embedding provider — deterministic vectors from text hashing.

    Generates vectors that are:
      - Deterministic: same text → same vector (seeded by SHA-256)
      - Correct dimensionality: 1024 to match Titan Embed v2
      - L2-normalized: unit vectors like real embeddings
      - Zero-dependency: no API calls, no model downloads

    Usage:
        Set EMBEDDING_PROVIDER=mock or APP_MODE=mock to activate.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the mock embedding provider.

        Args:
            settings: App settings (used to read embedding_model if needed).
        """
        self._settings = settings
        self._dimensions = DEFAULT_DIMENSIONS
        logger.info(
            "🎭 MockEmbeddingProvider initialized — %d-dim deterministic vectors",
            self._dimensions,
        )

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Embed a batch of texts into deterministic pseudo-random vectors.

        Args:
            texts: List of text strings to embed.
            model: Ignored — always uses 'mock-embedding-v1'.

        Returns:
            EmbeddingResult with one vector per input text.
        """
        from app.mock.factory import create_deterministic_vector

        logger.debug(
            "MockEmbedding.embed_texts called: %d texts, model=%s",
            len(texts),
            model or "mock-embedding-v1",
        )

        vectors = [
            create_deterministic_vector(text, self._dimensions)
            for text in texts
        ]

        return EmbeddingResult(
            vectors=vectors,
            model="mock-embedding-v1",
            usage={"prompt_tokens": sum(len(t.split()) for t in texts)},
        )

    async def embed_query(
        self,
        text: str,
        *,
        model: str | None = None,
    ) -> list[float]:
        """Embed a single query text. Convenience wrapper around embed_texts.

        Args:
            text: Query text to embed.
            model: Ignored.

        Returns:
            A single embedding vector as a list of floats.
        """
        result = await self.embed_texts([text], model=model)
        return result.vectors[0]


# ─── Provider Registration ────────────────────────────────────────────────────

register_provider("embedding", "mock", MockEmbeddingProvider)
