"""OpenAI embeddings provider — text-embedding-3-small implementation."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import Settings
from app.core.protocols import EmbeddingResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)

# Maximum batch size for OpenAI embeddings API
_MAX_BATCH_SIZE = 100


class OpenAIEmbeddingProvider:
    """OpenAI text embedding provider with batching support."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._default_model = settings.embedding_model

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Embed a batch of texts, auto-chunking into batches of 100."""
        target_model = model or self._default_model
        all_vectors: list[list[float]] = []
        total_usage: dict[str, int] = {"prompt_tokens": 0}

        # Process in batches
        for i in range(0, len(texts), _MAX_BATCH_SIZE):
            batch = texts[i : i + _MAX_BATCH_SIZE]

            response = await self._client.embeddings.create(
                model=target_model,
                input=batch,
            )

            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_vectors.extend([item.embedding for item in sorted_data])

            if response.usage:
                total_usage["prompt_tokens"] += response.usage.prompt_tokens

        return EmbeddingResult(
            vectors=all_vectors,
            model=target_model,
            usage=total_usage,
        )

    async def embed_query(
        self,
        text: str,
        *,
        model: str | None = None,
    ) -> list[float]:
        """Embed a single query text."""
        result = await self.embed_texts([text], model=model)
        return result.vectors[0]


# Self-register on import
register_provider("embedding", "openai", OpenAIEmbeddingProvider)
