"""environment.py — Centralized environment mode manager.

Reads APP_MODE from settings and provides helpers for runtime tier
detection, startup validation, and environment metadata.

Provider key requirements:
    bedrock    → AWS credentials (IAM role, env vars, or ~/.aws/credentials)
    openai     → OPENAI_API_KEY env var
    anthropic  → ANTHROPIC_API_KEY env var
    flashrank  → (none, runs locally)
    pgvector   → (none, uses DATABASE_URL)

Mode overview:
    mock       → All external calls faked, DB bypassed, auth bypassed.
    sandbox    → Real DB + sandbox API keys (Stripe test mode, etc.).
    production → Live everything.

Called by: main.py (startup), deps.py (auth), middleware.py (headers)
Depends on: config.py (Settings)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.config import get_settings

logger = logging.getLogger(__name__)

# ─── Valid Modes ──────────────────────────────────────────────────────────────

VALID_MODES = frozenset({"mock", "sandbox", "production"})

# WHY: Named constants prevent typos in string comparisons throughout
# the codebase. Import these instead of repeating raw strings.
MODE_MOCK = "mock"
MODE_SANDBOX = "sandbox"
MODE_PRODUCTION = "production"


# ─── Environment Info ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EnvironmentInfo:
    """Immutable snapshot of the current environment configuration.

    Returned by ``get_environment_info()`` and used in health responses,
    middleware headers, and frontend badge rendering.
    """

    mode: str                  # "mock" | "sandbox" | "production"
    app_env: str               # "development" | "staging" | "production"
    version: str               # Semantic version of the app
    features: dict[str, bool]  # Feature flags derived from mode


def get_environment_info() -> EnvironmentInfo:
    """Build an EnvironmentInfo snapshot from current settings.

    Returns:
        EnvironmentInfo with mode, env, version, and feature flags.
    """
    settings = get_settings()

    # WHY: Feature flags let the frontend conditionally show/hide UI
    # elements (e.g., the environment badge, debug tooling) based on
    # the active mode without hardcoding mode checks everywhere.
    features = {
        "mock_data": settings.is_mock,
        "auth_bypass": settings.is_mock,
        "sandbox_billing": settings.is_sandbox,
        "live_billing": settings.app_mode == MODE_PRODUCTION,
        "debug_tools": settings.app_mode != MODE_PRODUCTION,
    }

    return EnvironmentInfo(
        mode=settings.app_mode,
        app_env=settings.app_env,
        version="0.1.0",
        features=features,
    )


# ─── Startup Validation ──────────────────────────────────────────────────────


def _warn_missing_provider_keys(
    settings: Any,
    *,
    warn_only: bool = True,
    collect: list[str] | None = None,
) -> None:
    """Check that the active providers have their required keys/creds.

    Args:
        settings: The Settings instance.
        warn_only: If True, log warnings. If False, append to ``collect``.
        collect: List to append missing key names to (used in production mode).
    """
    def _flag(key_name: str, msg: str) -> None:
        if warn_only:
            logger.warning("%s — %s Consider APP_MODE=mock for frontend-only dev.", key_name, msg)
        elif collect is not None:
            collect.append(key_name)

    # ── LLM provider ─────────────────────────────────────────────────────
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        _flag("OPENAI_API_KEY", "Needed because LLM_PROVIDER=openai.")
    elif settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        _flag("ANTHROPIC_API_KEY", "Needed because LLM_PROVIDER=anthropic.")
    elif settings.llm_provider == "bedrock":
        # boto3 auto-discovers creds; check if something is available
        try:
            import boto3
            session = boto3.Session(region_name=settings.aws_region)
            creds = session.get_credentials()
            if creds is None:
                _flag(
                    "AWS_CREDENTIALS",
                    "Bedrock requires AWS creds (env vars, ~/.aws/credentials, or IAM role).",
                )
        except Exception:
            _flag("AWS_CREDENTIALS", "Could not verify AWS credentials for Bedrock.")

    # ── Embedding provider (same logic) ───────────────────────────────────
    if settings.embedding_provider == "openai" and not settings.openai_api_key:
        _flag("OPENAI_API_KEY", "Needed because EMBEDDING_PROVIDER=openai.")
    # Bedrock embeddings use same AWS creds — already checked above.


def validate_environment() -> None:
    """Validate environment configuration on startup.

    Checks:
        - APP_MODE is one of the valid modes.
        - Production mode has required API keys configured.
        - Logs warnings for sandbox mode with missing optional keys.

    Called by: main.py ``lifespan()`` on app startup.

    Raises:
        ValueError: If APP_MODE is not a recognized mode.
    """
    settings = get_settings()

    def _allowed_origins() -> list[str]:
        allowed = getattr(settings, "allowed_origins_list", None)
        if isinstance(allowed, list):
            return allowed
        raw = getattr(settings, "allowed_origins", "")
        return [origin.strip() for origin in str(raw).split(",") if origin.strip()]

    def _app_base_url() -> str:
        normalized = getattr(settings, "normalized_app_base_url", None)
        if isinstance(normalized, str) and normalized:
            return normalized
        return str(getattr(settings, "app_base_url", "")).rstrip("/")

    def _is_valid_http_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    if settings.app_mode not in VALID_MODES:
        raise ValueError(
            f"Invalid APP_MODE='{settings.app_mode}'. "
            f"Must be one of: {sorted(VALID_MODES)}"
        )

    allowed_origins = _allowed_origins()
    app_base_url = _app_base_url()

    if "*" in allowed_origins:
        if settings.app_mode == MODE_PRODUCTION:
            raise RuntimeError("ALLOWED_ORIGINS cannot contain '*' in production.")
        logger.warning("ALLOWED_ORIGINS contains '*'. This is unsafe outside local development.")

    invalid_origins = [origin for origin in allowed_origins if not _is_valid_http_url(origin)]
    if invalid_origins:
        raise RuntimeError(f"ALLOWED_ORIGINS has invalid URL(s): {', '.join(invalid_origins)}")

    if not _is_valid_http_url(app_base_url):
        raise RuntimeError("APP_BASE_URL must be a full http(s) URL (example: https://app.example.com).")

    logger.info(
        "Environment initialized: mode=%s, env=%s",
        settings.app_mode,
        settings.app_env,
    )

    if settings.app_mode == MODE_MOCK:
        logger.info(
            "🎭 MOCK MODE — All external calls are faked. "
            "No DB, no auth, no API keys needed."
        )
        return

    if settings.app_mode == MODE_SANDBOX:
        logger.info(
            "🧪 SANDBOX MODE — Real DB, sandbox API keys. "
            "Stripe uses test mode."
        )
        if not settings.nextauth_secret:
            logger.warning(
                "NEXTAUTH_SECRET/AUTH_SECRET not set — authenticated routes will reject tokens."
            )
        # WHY: Warn (don't crash) about missing optional keys in sandbox.
        # Developers may not have every service configured locally.
        if not settings.stripe_secret_key:
            logger.warning(
                "STRIPE_SECRET_KEY not set — billing endpoints will return 503."
            )
        _warn_missing_provider_keys(settings, warn_only=True)
        return

    # Production mode — stricter checks
    logger.info("🚀 PRODUCTION MODE — All services must be configured.")
    missing_keys: list[str] = []

    if not settings.stripe_secret_key:
        missing_keys.append("STRIPE_SECRET_KEY")
    if not settings.nextauth_secret:
        missing_keys.append("NEXTAUTH_SECRET")

    _warn_missing_provider_keys(settings, warn_only=False, collect=missing_keys)

    if missing_keys:
        message = (
            "Production mode requires these env vars: "
            + ", ".join(missing_keys)
        )
        logger.error(
            "Production mode requires these env vars: %s",
            ", ".join(missing_keys),
        )
        raise RuntimeError(message)


def to_dict(info: EnvironmentInfo) -> dict[str, Any]:
    """Serialize EnvironmentInfo to a JSON-safe dict.

    Used by the health endpoint and the ``/api/v1/environment`` route.

    Args:
        info: The EnvironmentInfo to serialize.

    Returns:
        Dict with mode, app_env, version, and features.
    """
    return {
        "mode": info.mode,
        "app_env": info.app_env,
        "version": info.version,
        "features": info.features,
    }
