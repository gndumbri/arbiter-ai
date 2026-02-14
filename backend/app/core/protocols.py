"""Provider protocols — abstract interfaces for all external dependencies.

Every external service (LLM, embeddings, vector store, reranker, document parser)
is defined as a Python Protocol. Business logic imports these protocols, never
concrete implementations. Swap providers by changing one env var.

Designed for future OpenAI Agents SDK integration — the LLMProvider protocol
is intentionally broad enough to support both simple completions and agentic
tool-calling workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ─── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)  # Full provider response for debugging


@dataclass
class EmbeddingResult:
    """Result of embedding one or more texts."""

    vectors: list[list[float]]
    model: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class VectorRecord:
    """A single vector with metadata for upsert."""

    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorMatch:
    """A single match from a vector query."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankResult:
    """A reranked document with score."""

    index: int  # Original index in input list
    score: float
    text: str


@dataclass
class ParsedSection:
    """A section extracted from a document."""

    header_path: str  # e.g., "Combat > Dice Roll > Modifiers"
    content: str
    page_number: int | None = None
    section_type: str = "text"  # "text" | "table" | "list" | "image_caption"


@dataclass
class ParsedDocument:
    """Full parsed output from a document."""

    sections: list[ParsedSection]
    metadata: dict[str, Any] = field(default_factory=dict)  # page_count, title, etc.
    raw_text: str = ""  # Full concatenated text for fallback


# ─── Protocols ─────────────────────────────────────────────────────────────────


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for language model completions.

    Implementations: OpenAI GPT, Anthropic Claude, OpenAI Agents SDK.
    """

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from the model."""
        ...

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> Any:
        """Stream a completion. Returns an async iterator of content chunks."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Abstract interface for text embedding."""

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Embed a batch of texts into vectors."""
        ...

    async def embed_query(
        self,
        text: str,
        *,
        model: str | None = None,
    ) -> list[float]:
        """Embed a single query text. Convenience wrapper."""
        ...


@runtime_checkable
class VectorStoreProvider(Protocol):
    """Abstract interface for vector storage and retrieval."""

    async def upsert(
        self,
        vectors: list[VectorRecord],
        *,
        namespace: str = "",
    ) -> int:
        """Upsert vectors. Returns count of vectors upserted."""
        ...

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        namespace: str = "",
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Query for similar vectors."""
        ...

    async def delete_by_ids(
        self,
        ids: list[str],
        *,
        namespace: str = "",
    ) -> None:
        """Delete vectors by their IDs."""
        ...

    async def delete_namespace(
        self,
        namespace: str,
    ) -> None:
        """Delete an entire namespace and all its vectors."""
        ...

    async def namespace_stats(
        self,
        namespace: str,
    ) -> dict[str, Any]:
        """Get stats for a namespace (vector_count, etc.)."""
        ...


@runtime_checkable
class RerankerProvider(Protocol):
    """Abstract interface for cross-encoder reranking."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
        model: str | None = None,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        ...


@runtime_checkable
class DocumentParserProvider(Protocol):
    """Abstract interface for document parsing (PDF → structured text)."""

    async def parse(
        self,
        file_path: str,
        *,
        max_pages: int | None = None,
    ) -> ParsedDocument:
        """Parse a document file into structured sections."""
        ...
