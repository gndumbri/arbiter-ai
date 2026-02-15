"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

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
    llm_provider: str = "openai"  # "openai" | "anthropic" | "bedrock"
    embedding_provider: str = "openai"  # "openai" | "bedrock"
    vector_store_provider: str = "pgvector"  # "pgvector" | "pinecone"
    reranker_provider: str = "cohere"  # "cohere" | "flashrank" | "none"
    parser_provider: str = "docling"  # "docling"

    # LLM model defaults
    llm_model: str = "gpt-4o"  # Primary model for verdicts
    llm_model_fast: str = "gpt-4o-mini"  # Cheap model for classification
    embedding_model: str = "text-embedding-3-small"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
