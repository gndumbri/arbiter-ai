"""pgvector-backed vector store — replaces Pinecone with Postgres-native storage.

WHY: Eliminates a managed service dependency (Pinecone) by storing embeddings
directly in our RDS Postgres instance. Queries use pgvector's <-> L2 distance
operator for similarity search, filtered by ruleset_id (the "namespace").

Protocol: Implements VectorStoreProvider (upsert, query, delete_by_ids,
delete_namespace, namespace_stats).

Architecture:
    - Vectors live in the `rule_chunks` table alongside their text content.
    - The "namespace" maps to `ruleset_id` (UUID stored as string in protocol).
    - Uses async SQLAlchemy sessions from the app's connection pool.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.core.protocols import VectorMatch, VectorRecord
from app.core.registry import register_provider

logger = logging.getLogger(__name__)


class PgVectorStoreProvider:
    """Postgres + pgvector vector store with namespace (ruleset_id) support.

    Each "namespace" maps to a ruleset_id in the rule_chunks table.
    Embeddings are stored as Vector(1024) columns, queried with L2 distance.
    """

    def __init__(self, settings: Settings) -> None:
        # WHY: We create our own engine + session factory so the provider
        # can be used both inside and outside of request context (e.g., in
        # seed scripts, Celery tasks).
        self._engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def upsert(
        self,
        vectors: list[VectorRecord],
        *,
        namespace: str = "",
    ) -> int:
        """Upsert vectors as rule_chunks rows.

        Each VectorRecord.id becomes the chunk's primary key.
        VectorRecord.metadata must include 'text' for the chunk content.
        Namespace is treated as the ruleset_id (UUID string).
        """
        from app.models.tables import RuleChunk

        async with self._session_factory() as session:
            ruleset_id = uuid.UUID(namespace) if namespace else None
            count = 0

            for v in vectors:
                # Check if chunk already exists (upsert semantics)
                existing = await session.execute(
                    select(RuleChunk).where(RuleChunk.id == uuid.UUID(v.id))
                )
                chunk = existing.scalar_one_or_none()

                if chunk:
                    # Update existing chunk
                    chunk.embedding = v.vector
                    chunk.chunk_text = v.metadata.get("text", chunk.chunk_text)
                else:
                    # Insert new chunk
                    session.add(RuleChunk(
                        id=uuid.UUID(v.id),
                        ruleset_id=ruleset_id,
                        chunk_index=v.metadata.get("chunk_index", 0),
                        chunk_text=v.metadata.get("text", ""),
                        embedding=v.vector,
                        section_header=v.metadata.get("section_header"),
                        page_number=v.metadata.get("page_number"),
                    ))
                count += 1

            await session.commit()

        logger.info("Upserted %d vectors to namespace '%s'", count, namespace)
        return count

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        namespace: str = "",
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Query for similar vectors using L2 distance (<->).

        Filters by ruleset_id (namespace). Returns matches with chunk text
        and metadata in the VectorMatch.metadata dict.
        """
        from app.models.tables import RuleChunk

        async with self._session_factory() as session:
            # WHY: pgvector's <-> operator uses L2 distance (lower = better).
            # We cast the query vector to a string that pgvector understands.
            distance_expr = RuleChunk.embedding.l2_distance(vector)

            stmt = (
                select(
                    RuleChunk,
                    distance_expr.label("distance"),
                )
                .order_by(distance_expr)
                .limit(top_k)
            )

            if namespace:
                stmt = stmt.where(RuleChunk.ruleset_id == uuid.UUID(namespace))

            result = await session.execute(stmt)
            rows = result.all()

        return [
            VectorMatch(
                id=str(chunk.id),
                # WHY: Convert L2 distance to a 0-1 similarity score.
                # 1/(1+d) maps [0,∞) → (0,1] — higher is more similar.
                score=1.0 / (1.0 + distance),
                metadata={
                    "text": chunk.chunk_text,
                    "section_header": chunk.section_header,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "ruleset_id": str(chunk.ruleset_id) if chunk.ruleset_id else None,
                },
            )
            for chunk, distance in rows
        ]

    async def delete_by_ids(
        self,
        ids: list[str],
        *,
        namespace: str = "",
    ) -> None:
        """Delete rule_chunk rows by their IDs."""
        from app.models.tables import RuleChunk

        async with self._session_factory() as session:
            chunk_ids = [uuid.UUID(i) for i in ids]
            await session.execute(
                delete(RuleChunk).where(RuleChunk.id.in_(chunk_ids))
            )
            await session.commit()

        logger.info("Deleted %d vectors from namespace '%s'", len(ids), namespace)

    async def delete_namespace(
        self,
        namespace: str,
    ) -> None:
        """Delete all rule_chunks for a given ruleset_id."""
        from app.models.tables import RuleChunk

        async with self._session_factory() as session:
            await session.execute(
                delete(RuleChunk).where(
                    RuleChunk.ruleset_id == uuid.UUID(namespace)
                )
            )
            await session.commit()

        logger.info("Deleted all vectors from namespace '%s'", namespace)

    async def namespace_stats(
        self,
        namespace: str,
    ) -> dict[str, Any]:
        """Get vector count for a ruleset_id."""
        from app.models.tables import RuleChunk

        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count(RuleChunk.id)).where(
                    RuleChunk.ruleset_id == uuid.UUID(namespace)
                )
            )
            count = result.scalar() or 0

        return {
            "vector_count": count,
            "namespace": namespace,
        }


# Self-register on import — same pattern as pinecone_store.py
register_provider("vector_store", "pgvector", PgVectorStoreProvider)
