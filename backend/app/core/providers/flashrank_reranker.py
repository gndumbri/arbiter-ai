"""FlashRank Reranker Provider implementation."""

from __future__ import annotations

import logging

# FlashRank is a local library, no API client needed
from flashrank import Ranker, RerankRequest

from app.config import Settings
from app.core.protocols import RerankerProvider, RerankResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class FlashRankRerankerProvider(RerankerProvider):
    """Local reranker using FlashRank (ms-marco-MiniLM-L-12-v2)."""

    def __init__(self, settings: Settings) -> None:
        # Load model into memory once at startup
        # Default model: ms-marco-MiniLM-L-12-v2 (~40MB)
        # Using cache_dir in /tmp or user cache would be ideal, but default is fine.
        logger.info("Initializing FlashRank model...")
        self.ranker = Ranker()
        logger.info("FlashRank model loaded.")

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
        model: str | None = None,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []

        # Construct input for FlashRank
        passages = [
            {"id": str(i), "text": doc}
            for i, doc in enumerate(documents)
        ]

        rerank_request = RerankRequest(query=query, passages=passages)
        results = self.ranker.rerank(rerank_request)

        # Sort by score descending and take top N
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_n]

        # Map back to protocol format
        output = []
        for res in sorted_results:
            original_index = int(res["id"])
            output.append(
                RerankResult(
                    index=original_index,
                    score=float(res["score"]),
                    text=documents[original_index],
                )
            )

        return output


register_provider("reranker", "flashrank", FlashRankRerankerProvider)
