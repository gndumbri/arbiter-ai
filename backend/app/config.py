"""Application settings via pydantic-settings.

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DEVELOPER QUICK-START  — What env vars do I need?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  APP_MODE controls the entire runtime tier:
#
#    mock        → Zero external deps.  All providers are faked, DB bypassed,
#                  auth bypassed.  Perfect for frontend-only development.
#                  Keys needed: NONE
#
#    sandbox     → Real Postgres DB, sandbox API keys (Stripe test mode, etc.).
#                  Full auth.  This is the default mode for local development.
#                  Keys needed: DATABASE_URL, NEXTAUTH_SECRET
#                  Optional: STRIPE_SECRET_KEY (billing),
#                            AWS creds (if using Bedrock for LLM/embeddings)
#
#    production  → Live everything.  All keys required.
#                  Keys needed: everything in sandbox + AWS creds + STRIPE_*
#
# ─── Provider Stack (defaults) ────────────────────────────────────────────────
#
#   Component        Default Provider    Env Var Override       API Key
#   ─────────        ────────────────    ────────────────       ───────
#   LLM              bedrock (Claude)    LLM_PROVIDER           AWS IAM creds
#   Embeddings       bedrock (Titan v2)  EMBEDDING_PROVIDER     AWS IAM creds
#   Vector Store     pgvector            VECTOR_STORE_PROVIDER  (none, uses DB)
#   Reranker         flashrank (local)   RERANKER_PROVIDER      (none, local)
#   PDF Parser       docling             PARSER_PROVIDER        (none, local)
#
#   To use OpenAI instead of Bedrock, set:
#     LLM_PROVIDER=openai
#     EMBEDDING_PROVIDER=openai
#     OPENAI_API_KEY=sk-...
#
# ─── AWS Credentials (for Bedrock) ────────────────────────────────────────────
#
#   Bedrock uses boto3, which auto-discovers credentials in this order:
#     1. Env vars:  AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
#     2. AWS profile:  AWS_PROFILE=your-profile  (reads ~/.aws/credentials)
#     3. IAM role:  Auto on EC2 / ECS / Lambda (no config needed)
#
#   You do NOT put AWS keys in this Settings class — boto3 handles them.
#   You only need to set AWS_REGION if not using us-east-1.
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
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
    # "mock"       = all fake data, no external calls, no DB, no auth
    # "sandbox"    = real DB + sandbox API keys (Stripe test mode, etc.)
    # "production" = live everything
    app_mode: str = "sandbox"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    # Comma-separated CORS origins.
    allowed_origins: str = "http://localhost:3000"
    # Canonical frontend URL used for absolute links (Stripe return URLs, invites).
    app_base_url: str = "http://localhost:3000"
    # Number of trusted reverse proxies in front of this app (0 = trust none).
    # AWS ALB + ECS is typically 1.
    trusted_proxy_hops: int = 0

    # Database  (async Postgres via SQLAlchemy + asyncpg)
    database_url: str = "postgresql+asyncpg://arbiter:arbiter_dev@localhost:5432/arbiter"

    # Redis  (session cache, rate limiting)
    redis_url: str = "redis://localhost:6379/0"

    # ─── LLM API Keys ────────────────────────────────────────────────────────
    # Only needed if you override the default Bedrock providers:
    #   LLM_PROVIDER=openai       → needs OPENAI_API_KEY
    #   LLM_PROVIDER=anthropic    → needs ANTHROPIC_API_KEY (direct API, not Bedrock)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ─── Auth ─────────────────────────────────────────────────────────────────
    # WHY: Support both NEXTAUTH_SECRET (backend docs) and AUTH_SECRET
    # (NextAuth v5 default) to prevent split-brain local config.
    nextauth_secret: str = Field(
        default="",
        validation_alias=AliasChoices("NEXTAUTH_SECRET", "AUTH_SECRET"),
    )

    # ─── Billing (Stripe) ─────────────────────────────────────────────────────
    # In sandbox mode, use Stripe test-mode keys (sk_test_..., whsec_test_...).
    # In production, use live keys.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # ─── Email (Brevo / Sendinblue) ───────────────────────────────────────────
    brevo_api_key: str = ""

    # ─── Crowdsource Ruling Cache ─────────────────────────────────────────────
    # When True, /rulings/cache-lookup checks public rulings before calling LLM.
    use_ruling_cache: bool = False

    # ─── AWS Bedrock ──────────────────────────────────────────────────────────
    # AWS credentials are handled by boto3 (env vars, profile, or IAM role).
    # Only aws_region and model IDs are configured here.
    aws_region: str = "us-east-1"
    bedrock_llm_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"

    # ─── Provider Selection ───────────────────────────────────────────────────
    # Swap implementations via env var.  In mock mode, the environment manager
    # auto-overrides all of these to "mock" providers.
    #
    # Available options per provider:
    #   llm_provider:          "bedrock" | "openai" | "anthropic" | "mock"
    #   embedding_provider:    "bedrock" | "openai" | "mock"
    #   vector_store_provider: "pgvector" | "mock"
    #   reranker_provider:     "flashrank" | "none" | "mock"
    #   parser_provider:       "docling"
    llm_provider: str = "bedrock"
    embedding_provider: str = "bedrock"
    vector_store_provider: str = "pgvector"
    reranker_provider: str = "flashrank"
    parser_provider: str = "docling"

    # Shared directory used by API + worker for temporary upload handoff.
    # In AWS, mount this path on shared EFS if using Celery workers.
    uploads_dir: str = "/tmp/arbiter_uploads"

    # ─── Model Defaults ──────────────────────────────────────────────────────
    # These are used when llm_provider=openai.  Bedrock model IDs are set above.
    llm_model: str = "gpt-4o"
    llm_model_fast: str = "gpt-4o-mini"
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

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a normalized list."""
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        if not origins:
            return [self.normalized_app_base_url]
        return origins

    @property
    def normalized_app_base_url(self) -> str:
        """Return APP_BASE_URL without a trailing slash."""
        return self.app_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
