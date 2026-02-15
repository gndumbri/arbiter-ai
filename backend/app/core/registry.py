"""Provider registry — resolves concrete implementations from config.

The registry is the single place where provider implementations are wired.
Business logic calls `registry.get_llm()` etc. and gets back a concrete
implementation based on the current config. Swapping providers is a one-line
env var change (e.g., LLM_PROVIDER=anthropic).

Usage:
    from app.core.registry import get_provider_registry

    registry = get_provider_registry()
    llm = registry.get_llm()
    embedder = registry.get_embedder()
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.core.protocols import (
    DocumentParserProvider,
    EmbeddingProvider,
    LLMProvider,
    RerankerProvider,
    VectorStoreProvider,
)

logger = logging.getLogger(__name__)

# ─── Provider Factory Map ──────────────────────────────────────────────────────
# Maps provider names to lazy import + construction functions.
# Adding a new provider = one entry here + one module in providers/.

_LLM_FACTORIES: dict[str, type] = {}
_EMBEDDING_FACTORIES: dict[str, type] = {}
_VECTOR_STORE_FACTORIES: dict[str, type] = {}
_RERANKER_FACTORIES: dict[str, type] = {}
_PARSER_FACTORIES: dict[str, type] = {}


def register_provider(
    category: str,
    name: str,
    cls: type,
) -> None:
    """Register a provider implementation.

    Called by provider modules on import, or manually in tests.

    Args:
        category: One of 'llm', 'embedding', 'vector_store', 'reranker', 'parser'
        name: Provider name (e.g., 'openai', 'anthropic', 'pinecone')
        cls: The provider class implementing the relevant Protocol
    """
    registry_map = {
        "llm": _LLM_FACTORIES,
        "embedding": _EMBEDDING_FACTORIES,
        "vector_store": _VECTOR_STORE_FACTORIES,
        "reranker": _RERANKER_FACTORIES,
        "parser": _PARSER_FACTORIES,
    }

    target = registry_map.get(category)
    if target is None:
        raise ValueError(f"Unknown provider category: {category}")

    target[name] = cls
    logger.info("Registered %s provider: %s", category, name)


class ProviderRegistry:
    """Singleton registry that resolves and caches provider instances."""

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._ensure_providers_loaded()

    def _ensure_providers_loaded(self) -> None:
        """Import all provider modules to trigger registration.

        Each provider module calls ``register_provider()`` on import,
        which adds it to the global factory maps. We import inside
        try/except so the app still works if a provider's dependencies
        aren't installed (e.g., Cohere SDK in a dev environment).
        """
        try:
            from app.core.providers import openai_llm  # noqa: F401
        except ImportError:
            logger.debug("openai_llm provider not available")
        try:
            from app.core.providers import openai_embeddings  # noqa: F401
        except ImportError:
            logger.debug("openai_embeddings provider not available")
        try:
            from app.core.providers import pinecone_store  # noqa: F401
        except ImportError:
            logger.debug("pinecone_store provider not available")
        try:
            from app.core.providers import cohere_reranker  # noqa: F401
        except ImportError:
            logger.debug("cohere_reranker provider not available")
        try:
            from app.core.providers import docling_parser  # noqa: F401
        except ImportError:
            logger.debug("docling_parser provider not available")
        try:
            from app.core.providers import bedrock_llm  # noqa: F401
        except ImportError:
            logger.debug("bedrock_llm provider not available")
        try:
            from app.core.providers import bedrock_embedding  # noqa: F401
        except ImportError:
            logger.debug("bedrock_embedding provider not available")
        try:
            from app.core.providers import flashrank_reranker  # noqa: F401
        except ImportError:
            logger.debug("flashrank_reranker provider not available")
        try:
            from app.core.providers import pg_vector_store  # noqa: F401
        except ImportError:
            logger.debug("pg_vector_store provider not available")

        # ─── Mock providers (always available — no external deps) ──────────
        # WHY: Mock providers have zero external dependencies, so they
        # should never fail to import. We still wrap in try/except for
        # consistency with the pattern above.
        try:
            from app.core.providers import (  # noqa: F401
                mock_embedding,
                mock_llm,
                mock_reranker,
                mock_vector_store,
            )
        except ImportError:
            logger.debug("mock providers not available")

    def _resolve(
        self,
        category: str,
        factories: dict[str, type],
        provider_name: str,
    ) -> Any:
        """Resolve and cache a provider instance."""
        cache_key = f"{category}:{provider_name}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        cls = factories.get(provider_name)
        if cls is None:
            available = list(factories.keys())
            raise ValueError(
                f"Unknown {category} provider: '{provider_name}'. "
                f"Available: {available}"
            )

        settings = get_settings()
        instance = cls(settings)
        self._instances[cache_key] = instance
        logger.info("Initialized %s provider: %s", category, provider_name)
        return instance

    def get_llm(self, override: str | None = None) -> LLMProvider:
        """Get the configured LLM provider."""
        name = override or get_settings().llm_provider
        return self._resolve("llm", _LLM_FACTORIES, name)

    def get_embedder(self, override: str | None = None) -> EmbeddingProvider:
        """Get the configured embedding provider."""
        name = override or get_settings().embedding_provider
        return self._resolve("embedding", _EMBEDDING_FACTORIES, name)

    def get_vector_store(self, override: str | None = None) -> VectorStoreProvider:
        """Get the configured vector store provider."""
        name = override or get_settings().vector_store_provider
        return self._resolve("vector_store", _VECTOR_STORE_FACTORIES, name)

    def get_reranker(self, override: str | None = None) -> RerankerProvider:
        """Get the configured reranker provider."""
        name = override or get_settings().reranker_provider
        return self._resolve("reranker", _RERANKER_FACTORIES, name)

    def get_parser(self, override: str | None = None) -> DocumentParserProvider:
        """Get the configured document parser provider."""
        name = override or get_settings().parser_provider
        return self._resolve("parser", _PARSER_FACTORIES, name)


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    """Get the singleton provider registry."""
    return ProviderRegistry()
