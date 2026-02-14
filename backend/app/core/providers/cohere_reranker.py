"""Cohere reranker provider — cross-encoder reranking."""

from __future__ import annotations

import logging

import cohere

from app.config import Settings
from app.core.protocols import RerankResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class CohereRerankerProvider:
    """Cohere Rerank v3 cross-encoder reranking."""

    def __init__(self, settings: Settings) -> None:
        self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
        self._default_model = "rerank-v3.5"

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

        target_model = model or self._default_model

        try:
            response = await self._client.rerank(
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
                model=target_model,
            )

            return [
                RerankResult(
                    index=result.index,
                    score=result.relevance_score,
                    text=documents[result.index],
                )
                for result in response.results
            ]
        except Exception as exc:
            logger.warning(
                "Reranker failed, falling back to original order: %s", str(exc)
            )
            # Graceful degradation — return documents in original order
            return [
                RerankResult(index=i, score=1.0 - (i * 0.01), text=doc)
                for i, doc in enumerate(documents[:top_n])
            ]


# Self-register on import
register_provider("reranker", "cohere", CohereRerankerProvider)
