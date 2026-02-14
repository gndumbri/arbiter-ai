"""Tests for provider protocol compliance."""

from __future__ import annotations

from app.core.protocols import (
    DocumentParserProvider,
    EmbeddingProvider,
    LLMProvider,
    RerankerProvider,
    VectorStoreProvider,
)


def test_openai_llm_implements_protocol() -> None:
    """OpenAI LLM provider should satisfy LLMProvider protocol."""
    from app.core.providers.openai_llm import OpenAILLMProvider

    assert issubclass(OpenAILLMProvider, LLMProvider)


def test_openai_embeddings_implements_protocol() -> None:
    """OpenAI embeddings provider should satisfy EmbeddingProvider protocol."""
    from app.core.providers.openai_embeddings import OpenAIEmbeddingProvider

    assert issubclass(OpenAIEmbeddingProvider, EmbeddingProvider)


def test_pinecone_implements_protocol() -> None:
    """Pinecone provider should satisfy VectorStoreProvider protocol."""
    from app.core.providers.pinecone_store import PineconeVectorStoreProvider

    assert issubclass(PineconeVectorStoreProvider, VectorStoreProvider)


def test_cohere_implements_protocol() -> None:
    """Cohere provider should satisfy RerankerProvider protocol."""
    from app.core.providers.cohere_reranker import CohereRerankerProvider

    assert issubclass(CohereRerankerProvider, RerankerProvider)


def test_docling_implements_protocol() -> None:
    """Docling provider should satisfy DocumentParserProvider protocol."""
    from app.core.providers.docling_parser import DoclingParserProvider

    assert issubclass(DoclingParserProvider, DocumentParserProvider)


def test_protocol_dataclasses() -> None:
    """Protocol data structures should be constructible."""
    from app.core.protocols import (
        EmbeddingResult,
        LLMResponse,
        Message,
        ParsedDocument,
        ParsedSection,
        RerankResult,
        VectorMatch,
        VectorRecord,
    )

    msg = Message(role="user", content="test")
    assert msg.role == "user"

    resp = LLMResponse(content="ok", model="gpt-4o")
    assert resp.finish_reason == "stop"

    emb = EmbeddingResult(vectors=[[0.1, 0.2]], model="test")
    assert len(emb.vectors) == 1

    vec = VectorRecord(id="v1", vector=[0.1], metadata={"key": "val"})
    assert vec.metadata["key"] == "val"

    match = VectorMatch(id="m1", score=0.95)
    assert match.score == 0.95

    rerank = RerankResult(index=0, score=0.9, text="text")
    assert rerank.index == 0

    section = ParsedSection(header_path="Setup", content="content")
    assert section.section_type == "text"

    doc = ParsedDocument(sections=[section])
    assert len(doc.sections) == 1
