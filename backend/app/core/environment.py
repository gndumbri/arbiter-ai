"""environment.py — Centralized environment mode manager.

Reads APP_MODE from settings and provides helpers for runtime tier
detection, startup validation, and environment metadata.

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

    if settings.app_mode not in VALID_MODES:
        raise ValueError(
            f"Invalid APP_MODE='{settings.app_mode}'. "
            f"Must be one of: {sorted(VALID_MODES)}"
        )

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
        # WHY: Warn (don't crash) about missing optional keys in sandbox.
        # Developers may not have every service configured locally.
        if not settings.stripe_secret_key:
            logger.warning(
                "STRIPE_SECRET_KEY not set — billing endpoints will return 503."
            )
        if not settings.openai_api_key and settings.llm_provider == "openai":
            logger.warning(
                "OPENAI_API_KEY not set — adjudication will fail. "
                "Consider APP_MODE=mock for frontend-only dev."
            )
        return

    # Production mode — stricter checks
    logger.info("🚀 PRODUCTION MODE — All services must be configured.")
    missing_keys: list[str] = []

    if not settings.stripe_secret_key:
        missing_keys.append("STRIPE_SECRET_KEY")
    if not settings.nextauth_secret:
        missing_keys.append("NEXTAUTH_SECRET")

    # WHY: Check the active LLM provider's key specifically rather than
    # requiring all keys. Users only need keys for their chosen provider.
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        missing_keys.append("OPENAI_API_KEY")
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        missing_keys.append("ANTHROPIC_API_KEY")

    if missing_keys:
        logger.error(
            "Production mode requires these env vars: %s",
            ", ".join(missing_keys),
        )


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
