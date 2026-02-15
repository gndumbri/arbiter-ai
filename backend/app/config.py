"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables.

    Controls all app behavior via env vars. The key environment knob is
    ``APP_MODE`` which selects the runtime tier:

    - **mock**       → All external calls faked, DB bypassed, auth bypassed.
    - **sandbox**    → Real DB + sandbox/test API keys. Full auth.
    - **production** → Live everything.

    Called by: Every module that needs configuration (via ``get_settings()``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─── Environment Mode ─────────────────────────────────────────────────────
    # WHY: A single env var that controls the entire runtime tier.
    # "mock" = all fake data, no external calls, no DB, no auth
    # "sandbox" = real DB + sandbox API keys (Stripe test mode, etc.)
    # "production" = live everything
    app_mode: str = "sandbox"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://arbiter:arbiter_dev@localhost:5432/arbiter"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "arbiter-rules"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # NextAuth
    nextauth_secret: str = ""  # Used to verify NextAuth JWT signatures

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Crowdsource ruling cache — when True, /rulings/cache-lookup returns
    # matching public rulings instead of calling the LLM.
    use_ruling_cache: bool = False

    # Reranker
    cohere_api_key: str = ""

    # AWS Bedrock
    aws_region: str = "us-east-1"
    bedrock_llm_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"

    # Provider selection — swap implementations via env var
    # WHY: In mock mode these are auto-overridden to "mock" providers
    # by the environment manager, so you don't need to change them.
    llm_provider: str = "openai"  # "openai" | "anthropic" | "bedrock" | "mock"
    embedding_provider: str = "openai"  # "openai" | "bedrock" | "mock"
    vector_store_provider: str = "pgvector"  # "pgvector" | "pinecone" | "mock"
    reranker_provider: str = "cohere"  # "cohere" | "flashrank" | "none" | "mock"
    parser_provider: str = "docling"  # "docling"

    # LLM model defaults
    llm_model: str = "gpt-4o"  # Primary model for verdicts
    llm_model_fast: str = "gpt-4o-mini"  # Cheap model for classification
    embedding_model: str = "text-embedding-3-small"

    # ─── Computed Properties ──────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        """True when app_env is explicitly set to 'production'."""
        return self.app_env == "production"

    @property
    def is_mock(self) -> bool:
        """True when running in mock mode — all external calls are faked."""
        return self.app_mode == "mock"

    @property
    def is_sandbox(self) -> bool:
        """True when running in sandbox mode — real DB, sandbox API keys."""
        return self.app_mode == "sandbox"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
