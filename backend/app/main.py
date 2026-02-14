"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import register_middleware
from app.api.routes import admin, billing, catalog, health, judge, parties, publishers, rules, rulings, sessions
from app.config import get_settings

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
    """Application startup and shutdown events."""
    logger.info("app_startup", env=get_settings().app_env)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
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
        allow_origins=settings.allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    register_middleware(app)

    # Routes
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(rules.router)
    app.include_router(judge.router)
    app.include_router(publishers.router)
    app.include_router(catalog.router)
    app.include_router(admin.router)
    app.include_router(rulings.router)
    app.include_router(parties.router)
    app.include_router(billing.router)

    return app


app = create_app()
