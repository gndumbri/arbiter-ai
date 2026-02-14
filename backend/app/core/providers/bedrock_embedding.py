"""AWS Bedrock Embedding Provider implementation."""

from __future__ import annotations

import json
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings
from app.core.protocols import EmbeddingProvider, EmbeddingResult
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class BedrockEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using AWS Bedrock (Titan Embeddings v2)."""

    def __init__(self, settings: Settings) -> None:
        self.client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self.model_id = settings.bedrock_embed_model_id

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Embed a batch of texts into vectors."""
        target_model = model or self.model_id
        vectors = []
        input_tokens = 0

        # Titan v2 doesn't support batching in a single API call (unlike OpenAI)
        # We must iterate. Parallelism could be added with asyncio.gather if latency is an issue.
        for text in texts:
            try:
                # Titan v2 Payload
                body = json.dumps({
                    "inputText": text,
                    "dimensions": 1024,  # Optimized for cost/performance
                    "normalize": True
                })

                response = self.client.invoke_model(
                    modelId=target_model,
                    body=body,
                    accept="application/json",
                    contentType="application/json"
                )

                response_body = json.loads(response.get("body").read())
                embedding = response_body.get("embedding")
                token_count = response_body.get("inputTextTokenCount", 0)

                vectors.append(embedding)
                input_tokens += token_count

            except (BotoCoreError, ClientError) as e:
                logger.error(f"Bedrock Embedding API error: {e}", exc_info=True)
                raise

        return EmbeddingResult(
            vectors=vectors,
            model=target_model,
            usage={"prompt_tokens": input_tokens, "total_tokens": input_tokens}
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


register_provider("embedding", "bedrock", BedrockEmbeddingProvider)
