"""FastAPI application factory.

Builds the FastAPI app with middleware, routes, and lifespan events.
Route selection is controlled by APP_MODE:
    - mock       → Mock routes only (no DB, no auth, no external calls)
    - sandbox    → Real routes with sandbox/test API keys
    - production → Real routes with live API keys

Called by: Uvicorn (``uv run uvicorn app.main:app``)
Depends on: config.py, environment.py, routes/*, middleware.py
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import register_middleware
from app.config import get_settings
from app.core.environment import validate_environment

_settings = get_settings()
_log_level = getattr(logging, _settings.log_level.upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if not _settings.is_production
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events.

    Validates the environment configuration and logs the active mode.
    """
    # WHY: validate_environment() checks that APP_MODE is valid and
    # warns about missing API keys in sandbox/production mode.
    validate_environment()
    logger.info(
        "app_startup",
        env=get_settings().app_env,
        mode=get_settings().app_mode,
        llm_provider=get_settings().llm_provider,
        embedding_provider=get_settings().embedding_provider,
        vector_store_provider=get_settings().vector_store_provider,
        reranker_provider=get_settings().reranker_provider,
    )
    yield
    logger.info("app_shutdown")


def _register_mock_routes(app: FastAPI) -> None:
    """Mount mock routes — called only when APP_MODE=mock.

    WHY: In mock mode, we replace ALL real routes with mock equivalents.
    This means no database, no auth, and no external API calls are
    needed. The mock routes return fixture data from mock/fixtures.py.
    Same URL paths as real routes so the frontend doesn't need any changes.
    """
    from app.api.routes.mock_routes import api_router, router

    app.include_router(router)    # Root-level routes (/health)
    app.include_router(api_router)  # API routes (/api/v1/*)

    logger.info(
        "🎭 Mock routes mounted — all endpoints return fixture data. "
        "No DB, no auth, no external API calls."
    )


def _register_real_routes(app: FastAPI) -> None:
    """Mount real routes — called for sandbox and production modes.

    All routes use real database, authentication, and configured
    external API providers (OpenAI, Stripe, etc.).
    """
    from app.api.routes import (
        admin,
        agents,
        billing,
        catalog,
        health,
        judge,
        library,
        parties,
        publishers,
        rules,
        rulings,
        sessions,
        users,
    )

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(sessions.router)
    app.include_router(rules.router)
    app.include_router(judge.router)
    app.include_router(publishers.router)
    app.include_router(catalog.router)
    app.include_router(admin.router)
    app.include_router(rulings.router)
    app.include_router(parties.router)
    app.include_router(billing.router)
    app.include_router(library.router)
    app.include_router(users.router)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Route selection:
        APP_MODE=mock       → mock_routes.py only
        APP_MODE=sandbox    → all real routes
        APP_MODE=production → all real routes

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Arbiter AI",
        description="RAG-based adjudication engine for board game rules",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (logging, rate limiting, etc.)
    register_middleware(app)

    # ─── Route Selection ──────────────────────────────────────────────────
    # WHY: In mock mode we skip importing real routes entirely, which
    # means the app doesn't need a running database, Redis, or any
    # API keys to start. This is ideal for frontend development.
    if settings.is_mock:
        _register_mock_routes(app)
    else:
        _register_real_routes(app)

    return app


app = create_app()
