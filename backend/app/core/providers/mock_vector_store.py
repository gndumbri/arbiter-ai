"""mock_vector_store.py — In-memory vector store for testing without Pinecone/pgvector.

Implements the VectorStoreProvider protocol with a simple in-memory dict.
Vectors are stored in RAM and lost on restart — perfect for mock mode
where persistence isn't needed.

Called by: AdjudicationEngine (via registry) when VECTOR_STORE_PROVIDER=mock
Depends on: protocols.py (VectorStoreProvider)
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.protocols import VectorMatch, VectorRecord
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class MockVectorStoreProvider:
    """In-memory vector store — stores and queries vectors in RAM.

    Features:
      - Full CRUD: upsert, query, delete by ID, delete namespace
      - Cosine similarity search (simplified dot product on normalized vectors)
      - Namespace isolation (separate dict per namespace)
      - Pre-seeded with fixture data for realistic demo queries

    Usage:
        Set VECTOR_STORE_PROVIDER=mock or APP_MODE=mock to activate.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the in-memory vector store.

        Args:
            settings: App settings (not used, but required by registry interface).
        """
        self._settings = settings
        # WHY: Dict[namespace][id] = VectorRecord for O(1) lookups.
        # Each namespace is a separate dict to mimic Pinecone's
        # namespace isolation behavior.
        self._store: dict[str, dict[str, VectorRecord]] = {}
        logger.info("🎭 MockVectorStoreProvider initialized — in-memory storage")

    async def upsert(
        self,
        vectors: list[VectorRecord],
        *,
        namespace: str = "",
    ) -> int:
        """Store vectors in memory, overwriting existing IDs.

        Args:
            vectors: List of VectorRecord objects to upsert.
            namespace: Namespace to store vectors in (default: empty string).

        Returns:
            Number of vectors upserted.
        """
        if namespace not in self._store:
            self._store[namespace] = {}

        for record in vectors:
            self._store[namespace][record.id] = record

        logger.debug(
            "MockVectorStore.upsert: %d vectors into namespace='%s' (total: %d)",
            len(vectors),
            namespace,
            len(self._store[namespace]),
        )
        return len(vectors)

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        namespace: str = "",
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Find similar vectors using simplified cosine similarity.

        For mock mode, we use dot product on normalized vectors as a
        reasonable approximation of cosine similarity.

        Args:
            vector: Query vector.
            top_k: Maximum number of results to return.
            namespace: Namespace to search in.
            filter: Metadata filter (basic key-value matching).

        Returns:
            List of VectorMatch objects sorted by similarity score (descending).
        """
        ns_store = self._store.get(namespace, {})

        if not ns_store:
            logger.debug(
                "MockVectorStore.query: namespace='%s' is empty, returning mock results",
                namespace,
            )
            # WHY: Return pre-seeded mock results even from empty stores
            # so the adjudication engine always has something to work with.
            return self._generate_mock_results(top_k)

        # Calculate dot-product similarity for each stored vector
        scored: list[tuple[str, float, dict[str, Any]]] = []
        for record_id, record in ns_store.items():
            # WHY: Apply metadata filter if provided. Simple key-value
            # matching — production stores support more complex filters.
            if filter and not all(
                record.metadata.get(k) == v
                for k, v in filter.items()
            ):
                continue

            # Dot product on (presumably normalized) vectors
            score = sum(a * b for a, b in zip(vector, record.vector, strict=False))
            scored.append((record_id, score, record.metadata))

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            VectorMatch(id=rid, score=score, metadata=meta)
            for rid, score, meta in scored[:top_k]
        ]

    def _generate_mock_results(self, top_k: int) -> list[VectorMatch]:
        """Generate synthetic search results when the store is empty.

        Returns realistic-looking matches that the adjudication engine
        can use to build a verdict.

        Args:
            top_k: Number of results to generate.

        Returns:
            List of VectorMatch objects with decreasing scores.
        """
        mock_chunks = [
            {
                "text": "Players take turns clockwise. On your turn, you must perform exactly one action.",
                "source": "Core Rulebook",
                "page": 15,
                "section": "Turn Structure",
            },
            {
                "text": "When making an attack roll, roll a d20 and add applicable modifiers.",
                "source": "Core Rulebook",
                "page": 42,
                "section": "Combat — Attack Rolls",
            },
            {
                "text": "A character can move a distance up to their speed during their turn.",
                "source": "Core Rulebook",
                "page": 38,
                "section": "Movement",
            },
            {
                "text": "Resources can be traded between players during the active player's turn.",
                "source": "Core Rulebook",
                "page": 10,
                "section": "Trading",
            },
            {
                "text": "At the end of each round, all players draw new cards from the deck.",
                "source": "Core Rulebook",
                "page": 22,
                "section": "End of Round",
            },
        ]

        results = []
        for i, chunk in enumerate(mock_chunks[:top_k]):
            # WHY: Decreasing scores simulate real search where the
            # top result is most relevant and scores taper off.
            score = 0.95 - (i * 0.08)
            results.append(
                VectorMatch(
                    id=f"mock-chunk-{i}",
                    score=max(score, 0.3),
                    metadata=chunk,
                )
            )

        return results

    async def delete_by_ids(
        self,
        ids: list[str],
        *,
        namespace: str = "",
    ) -> None:
        """Delete vectors by their IDs.

        Args:
            ids: List of vector IDs to delete.
            namespace: Namespace to delete from.
        """
        ns_store = self._store.get(namespace, {})
        for vid in ids:
            ns_store.pop(vid, None)
        logger.debug(
            "MockVectorStore.delete_by_ids: %d IDs from namespace='%s'",
            len(ids),
            namespace,
        )

    async def delete_namespace(self, namespace: str) -> None:
        """Delete an entire namespace and all its vectors.

        Args:
            namespace: Namespace to delete.
        """
        self._store.pop(namespace, None)
        logger.debug("MockVectorStore.delete_namespace: '%s'", namespace)

    async def namespace_stats(self, namespace: str) -> dict[str, Any]:
        """Get stats for a namespace.

        Args:
            namespace: Namespace to get stats for.

        Returns:
            Dict with vector_count and namespace name.
        """
        ns_store = self._store.get(namespace, {})
        return {
            "vector_count": len(ns_store),
            "namespace": namespace,
        }


# ─── Provider Registration ────────────────────────────────────────────────────

register_provider("vector_store", "mock", MockVectorStoreProvider)
