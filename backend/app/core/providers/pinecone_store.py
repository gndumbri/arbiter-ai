"""Pinecone vector store provider — serverless implementation."""

from __future__ import annotations

import logging
from typing import Any

from pinecone import Pinecone

from app.config import Settings
from app.core.protocols import VectorMatch, VectorRecord
from app.core.registry import register_provider

logger = logging.getLogger(__name__)

# Pinecone upsert batch size
_UPSERT_BATCH_SIZE = 100


class PineconeVectorStoreProvider:
    """Pinecone serverless vector store with namespace support."""

    def __init__(self, settings: Settings) -> None:
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = self._pc.Index(settings.pinecone_index_name)

    async def upsert(
        self,
        vectors: list[VectorRecord],
        *,
        namespace: str = "",
    ) -> int:
        """Upsert vectors in batches of 100."""
        total = 0
        for i in range(0, len(vectors), _UPSERT_BATCH_SIZE):
            batch = vectors[i : i + _UPSERT_BATCH_SIZE]
            upsert_data = [
                {
                    "id": v.id,
                    "values": v.vector,
                    "metadata": v.metadata,
                }
                for v in batch
            ]
            result = self._index.upsert(
                vectors=upsert_data,
                namespace=namespace,
            )
            total += result.get("upserted_count", len(batch))

        logger.info(
            "Upserted %d vectors to namespace '%s'",
            total,
            namespace,
        )
        return total

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        namespace: str = "",
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Query for similar vectors with optional metadata filters."""
        params: dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "namespace": namespace,
            "include_metadata": True,
        }
        if filter:
            params["filter"] = filter

        result = self._index.query(**params)

        return [
            VectorMatch(
                id=match["id"],
                score=match["score"],
                metadata=match.get("metadata", {}),
            )
            for match in result.get("matches", [])
        ]

    async def delete_by_ids(
        self,
        ids: list[str],
        *,
        namespace: str = "",
    ) -> None:
        """Delete vectors by their IDs."""
        self._index.delete(ids=ids, namespace=namespace)
        logger.info("Deleted %d vectors from namespace '%s'", len(ids), namespace)

    async def delete_namespace(
        self,
        namespace: str,
    ) -> None:
        """Delete all vectors in a namespace."""
        self._index.delete(delete_all=True, namespace=namespace)
        logger.info("Deleted all vectors from namespace '%s'", namespace)

    async def namespace_stats(
        self,
        namespace: str,
    ) -> dict[str, Any]:
        """Get namespace statistics."""
        stats = self._index.describe_index_stats()
        ns_stats = stats.get("namespaces", {}).get(namespace, {})
        return {
            "vector_count": ns_stats.get("vector_count", 0),
            "namespace": namespace,
        }


# Self-register on import
register_provider("vector_store", "pinecone", PineconeVectorStoreProvider)
