"""Middleware for request logging, error handling, request IDs, and environment tagging.

Middleware stack (executed in reverse registration order):
    1. RequestIDMiddleware  → Assigns unique X-Request-ID to every request
    2. LoggingMiddleware    → Logs method, path, status, and duration
    3. EnvironmentMiddleware → Adds X-Arbiter-Env header (mock|sandbox|production)
    4. ErrorHandlerMiddleware → Catches unhandled exceptions → JSON error response

The X-Arbiter-Env header is especially useful for:
    - Frontend EnvironmentBadge component (reads header to show mode)
    - DevTools network panel (quickly see which tier each request uses)
    - Load balancer health checks (verify correct environment)

Called by: main.py (``register_middleware()``)
Depends on: config.py (Settings)
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request/response.

    If the client sends an ``X-Request-ID`` header, we reuse it.
    Otherwise, a new UUID is generated. The ID is attached to both
    ``request.state.request_id`` and the response ``X-Request-ID`` header.
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        request_id = getattr(request.state, "request_id", "unknown")

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response


class EnvironmentMiddleware(BaseHTTPMiddleware):
    """Add ``X-Arbiter-Env`` response header on every request.

    This header tells the frontend (and devtools) which environment
    tier is active:

        X-Arbiter-Env: mock       → All fake data, no external calls
        X-Arbiter-Env: sandbox    → Real DB + sandbox API keys
        X-Arbiter-Env: production → Live everything

    WHY: Developers working on the frontend need to know at a glance
    which backend mode they're hitting. The EnvironmentBadge component
    reads this header to render the mode badge. In devtools, you can
    filter by this header to verify mock vs real responses.
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        response = await call_next(request)
        settings = get_settings()
        # WHY: Always include the header so every response is self-
        # documenting. Production mode also gets the header — it's
        # harmless metadata, not a security risk.
        response.headers["X-Arbiter-Env"] = settings.app_mode
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return consistent JSON error responses.

    Logs the full traceback via structlog and returns a sanitized
    error response to the client. Never leaks internal details
    to the end user.
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.exception(
                "unhandled_error",
                error=str(exc),
                request_id=request_id,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "The Arbiter hit a snag. Our team has been notified — please try again shortly!",
                    }
                },
            )


def register_middleware(app: FastAPI) -> None:
    """Register all middleware in the correct order.

    Starlette middleware is executed in reverse registration order,
    so we register in this order:
        1. ErrorHandler    (registered first → executed last → outermost wrapper)
        2. SecurityHeaders (injects hardening headers)
        3. IPRateLimit     (per-IP rate limiting — catches unauthenticated abuse)
        4. Environment     (injects X-Arbiter-Env header)
        5. Logging         (logs request details)
        6. RequestID       (registered last → executed first → assigns request ID)
    """
    from app.api.ip_rate_limit import IPRateLimitMiddleware

    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(IPRateLimitMiddleware)
    app.add_middleware(EnvironmentMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security hardening headers to every response.

    WHY: These headers instruct browsers to enable built-in protections:
    - X-Content-Type-Options: Prevents MIME-type sniffing attacks
    - X-Frame-Options: Prevents clickjacking by denying framing
    - Referrer-Policy: Limits referrer leakage to same-origin
    - Permissions-Policy: Disables access to sensitive device APIs

    These are defense-in-depth measures — they work alongside CSP (which
    is typically added by the frontend/CDN layer).
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
