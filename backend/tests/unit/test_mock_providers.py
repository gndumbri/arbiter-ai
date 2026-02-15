"""Tests for the mock providers (LLM, embedding, vector store, reranker).

Validates that all mock providers:
  - Satisfy their respective Protocol interfaces
  - Return correct response shapes
  - Work with zero external dependencies

Run with: cd backend && uv run pytest tests/unit/test_mock_providers.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.protocols import LLMResponse, Message

# ─── MockLLMProvider Tests ────────────────────────────────────────────────────


class TestMockLLMProvider:
    """Tests for the mock LLM provider."""

    @pytest.fixture
    def provider(self):
        """Create a MockLLMProvider instance."""
        from app.core.providers.mock_llm import MockLLMProvider
        settings = MagicMock()
        return MockLLMProvider(settings)

    @pytest.mark.anyio
    async def test_complete_returns_llm_response(self, provider):
        """complete() should return a valid LLMResponse."""
        messages = [
            Message(role="system", content="You are a rules judge."),
            Message(role="user", content="Can I attack twice?"),
        ]
        result = await provider.complete(messages)

        assert isinstance(result, LLMResponse)
        assert result.model == "mock-llm-v1"
        assert result.content  # Non-empty
        assert result.finish_reason == "stop"
        assert "prompt_tokens" in result.usage

    @pytest.mark.anyio
    async def test_complete_keyword_matching(self, provider):
        """complete() should match 'attack' keyword to canned verdict."""
        messages = [Message(role="user", content="How does attack work?")]
        result = await provider.complete(messages)

        # The attack-keyword verdict should mention "attack"
        assert "attack" in result.content.lower()

    @pytest.mark.anyio
    async def test_complete_json_mode(self, provider):
        """complete() with response_format should return JSON string."""
        messages = [Message(role="user", content="Some question")]
        result = await provider.complete(
            messages,
            response_format={"type": "json_object"},
        )

        import json
        parsed = json.loads(result.content)
        assert "verdict" in parsed
        assert "confidence" in parsed

    @pytest.mark.anyio
    async def test_stream_yields_chunks(self, provider):
        """stream() should yield string chunks."""
        messages = [Message(role="user", content="Test question")]
        stream = await provider.stream(messages)

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)


# ─── MockEmbeddingProvider Tests ──────────────────────────────────────────────


class TestMockEmbeddingProvider:
    """Tests for the mock embedding provider."""

    @pytest.fixture
    def provider(self):
        """Create a MockEmbeddingProvider instance."""
        from app.core.providers.mock_embedding import MockEmbeddingProvider
        settings = MagicMock()
        return MockEmbeddingProvider(settings)

    @pytest.mark.anyio
    async def test_embed_texts_returns_correct_dimensions(self, provider):
        """embed_texts() should return 1024-dim vectors."""
        result = await provider.embed_texts(["hello world", "test query"])

        assert len(result.vectors) == 2
        assert len(result.vectors[0]) == 1024
        assert len(result.vectors[1]) == 1024

    @pytest.mark.anyio
    async def test_embed_texts_deterministic(self, provider):
        """Same text should produce the same vector every time."""
        result1 = await provider.embed_texts(["hello world"])
        result2 = await provider.embed_texts(["hello world"])

        assert result1.vectors[0] == result2.vectors[0]

    @pytest.mark.anyio
    async def test_embed_texts_different_inputs_differ(self, provider):
        """Different texts should produce different vectors."""
        result = await provider.embed_texts(["hello", "goodbye"])

        assert result.vectors[0] != result.vectors[1]

    @pytest.mark.anyio
    async def test_embed_query_returns_single_vector(self, provider):
        """embed_query() should return a single list of floats."""
        vector = await provider.embed_query("test query")

        assert isinstance(vector, list)
        assert len(vector) == 1024
        assert all(isinstance(v, float) for v in vector)


# ─── MockVectorStoreProvider Tests ────────────────────────────────────────────


class TestMockVectorStoreProvider:
    """Tests for the in-memory vector store."""

    @pytest.fixture
    def provider(self):
        """Create a MockVectorStoreProvider instance."""
        from app.core.providers.mock_vector_store import MockVectorStoreProvider
        settings = MagicMock()
        return MockVectorStoreProvider(settings)

    @pytest.mark.anyio
    async def test_query_empty_store_returns_mock_results(self, provider):
        """query() on empty store should return pre-seeded mock results."""
        results = await provider.query(
            vector=[0.1] * 1024,
            top_k=3,
            namespace="test",
        )

        assert len(results) == 3
        assert results[0].score > results[1].score  # Descending scores

    @pytest.mark.anyio
    async def test_upsert_and_query_round_trip(self, provider):
        """Upserted vectors should be retrievable via query()."""
        from app.core.protocols import VectorRecord

        records = [
            VectorRecord(
                id="v1",
                vector=[1.0] + [0.0] * 1023,
                metadata={"text": "test doc"},
            ),
        ]
        count = await provider.upsert(records, namespace="test-ns")
        assert count == 1

        results = await provider.query(
            vector=[1.0] + [0.0] * 1023,
            top_k=5,
            namespace="test-ns",
        )
        assert len(results) == 1
        assert results[0].id == "v1"

    @pytest.mark.anyio
    async def test_delete_by_ids(self, provider):
        """delete_by_ids() should remove vectors from the store."""
        from app.core.protocols import VectorRecord

        records = [
            VectorRecord(id="v1", vector=[0.0] * 1024, metadata={}),
            VectorRecord(id="v2", vector=[0.0] * 1024, metadata={}),
        ]
        await provider.upsert(records, namespace="ns")
        await provider.delete_by_ids(["v1"], namespace="ns")

        stats = await provider.namespace_stats("ns")
        assert stats["vector_count"] == 1

    @pytest.mark.anyio
    async def test_delete_namespace(self, provider):
        """delete_namespace() should remove entire namespace."""
        from app.core.protocols import VectorRecord

        await provider.upsert(
            [VectorRecord(id="v1", vector=[0.0] * 1024, metadata={})],
            namespace="doomed",
        )
        await provider.delete_namespace("doomed")

        stats = await provider.namespace_stats("doomed")
        assert stats["vector_count"] == 0


# ─── MockRerankerProvider Tests ───────────────────────────────────────────────


class TestMockRerankerProvider:
    """Tests for the passthrough reranker."""

    @pytest.fixture
    def provider(self):
        """Create a MockRerankerProvider instance."""
        from app.core.providers.mock_reranker import MockRerankerProvider
        settings = MagicMock()
        return MockRerankerProvider(settings)

    @pytest.mark.anyio
    async def test_rerank_preserves_order(self, provider):
        """rerank() should return documents in original order."""
        docs = ["first doc", "second doc", "third doc"]
        results = await provider.rerank("test query", docs, top_n=3)

        assert len(results) == 3
        assert results[0].text == "first doc"
        assert results[1].text == "second doc"

    @pytest.mark.anyio
    async def test_rerank_scores_decrease(self, provider):
        """rerank() scores should decrease linearly."""
        docs = ["a", "b", "c", "d"]
        results = await provider.rerank("query", docs, top_n=4)

        for i in range(len(results) - 1):
            assert results[i].score > results[i + 1].score

    @pytest.mark.anyio
    async def test_rerank_top_n_limits_results(self, provider):
        """rerank() should respect the top_n parameter."""
        docs = ["a", "b", "c", "d", "e"]
        results = await provider.rerank("query", docs, top_n=2)

        assert len(results) == 2
