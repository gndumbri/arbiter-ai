"""mock_reranker.py — Mock reranker provider for testing without Cohere/FlashRank.

Implements the RerankerProvider protocol with a passthrough that returns
documents in their original order with linearly decreasing scores.
No external calls, no model downloads.

Called by: AdjudicationEngine (via registry) when RERANKER_PROVIDER=mock
Depends on: protocols.py (RerankerProvider)
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.protocols import RerankResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class MockRerankerProvider:
    """Passthrough reranker — returns documents in order with decreasing scores.

    WHY: In mock mode we don't need actual cross-encoder reranking.
    Returning documents in their original (already-sorted-by-vector-score)
    order is a reasonable approximation. Scores decrease linearly
    so the top result is clearly the "best" match.

    Usage:
        Set RERANKER_PROVIDER=mock or APP_MODE=mock to activate.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the mock reranker.

        Args:
            settings: App settings (not used, but required by registry interface).
        """
        self._settings = settings
        logger.info("🎭 MockRerankerProvider initialized — passthrough mode")

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
        model: str | None = None,
    ) -> list[RerankResult]:
        """Return documents in their original order with decreasing scores.

        Args:
            query: The search query (logged but not used for ranking).
            documents: List of document texts to "rerank".
            top_n: Maximum number of results to return.
            model: Ignored — no model needed.

        Returns:
            List of RerankResult objects with linearly decreasing scores.
        """
        logger.debug(
            "MockReranker.rerank: query='%s', %d documents, top_n=%d",
            query[:50],
            len(documents),
            top_n,
        )

        # WHY: Linear score decay from 0.95 down. The exact values don't
        # matter much for mock mode — what matters is maintaining sort
        # order so the adjudication engine's top-reranked flow works.
        results = []
        for i, doc in enumerate(documents[:top_n]):
            score = max(0.95 - (i * 0.07), 0.1)
            results.append(
                RerankResult(
                    index=i,
                    score=score,
                    text=doc,
                )
            )

        return results


# ─── Provider Registration ────────────────────────────────────────────────────

register_provider("reranker", "mock", MockRerankerProvider)
