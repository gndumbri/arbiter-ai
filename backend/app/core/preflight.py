"""Preflight readiness checks for sandbox/production environments.

Run these checks before deploying or promoting an environment to catch
configuration/dependency regressions early.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.core.environment import validate_environment
from app.core.protocols import Message
from app.core.registry import get_provider_registry


@dataclass(frozen=True)
class CheckResult:
    """A single preflight check outcome."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """Aggregated preflight report."""

    ok: bool
    mode: str
    timestamp_utc: str
    checks: list[CheckResult]

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "timestamp_utc": self.timestamp_utc,
            "checks": [
                {"name": item.name, "ok": item.ok, "detail": item.detail}
                for item in self.checks
            ],
        }


def _pass(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, ok=True, detail=detail)


def _fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, ok=False, detail=detail)


def check_environment(expected_mode: str | None = None) -> CheckResult:
    """Validate env and optionally enforce the expected APP_MODE."""
    settings = get_settings()
    try:
        validate_environment()
    except Exception as exc:
        return _fail("environment", f"validation failed: {exc}")

    if expected_mode and settings.app_mode != expected_mode:
        return _fail(
            "environment",
            f"APP_MODE={settings.app_mode!r} but expected {expected_mode!r}",
        )

    return _pass(
        "environment",
        f"validated (mode={settings.app_mode}, env={settings.app_env})",
    )


async def check_database() -> CheckResult:
    """Verify database connectivity."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return _pass("database", "connection ok")
    except Exception as exc:
        return _fail("database", f"connection failed: {exc}")
    finally:
        await engine.dispose()


async def check_redis() -> CheckResult:
    """Verify Redis connectivity."""
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        pong = await redis.ping()
        if pong is True:
            return _pass("redis", "ping ok")
        return _fail("redis", f"unexpected ping response: {pong!r}")
    except Exception as exc:
        return _fail("redis", f"ping failed: {exc}")
    finally:
        with contextlib.suppress(Exception):
            await redis.aclose()


async def check_providers(
    *,
    probe_embedding: bool = False,
    probe_llm: bool = False,
) -> CheckResult:
    """Verify provider instantiation and optional live calls."""
    try:
        registry = get_provider_registry()
        llm = registry.get_llm()
        embedder = registry.get_embedder()
        vector_store = registry.get_vector_store()
        reranker = registry.get_reranker()
        parser = registry.get_parser()

        # Touch vector store with a harmless namespace-stats call.
        namespace = str(uuid.uuid4())
        _ = await vector_store.namespace_stats(namespace)

        if probe_embedding:
            _ = await embedder.embed_query("preflight readiness check")

        if probe_llm:
            _ = await llm.complete(
                messages=[
                    Message(
                        role="user",
                        content="Reply with exactly: OK",
                    )
                ],
                temperature=0.0,
                max_tokens=16,
            )

        details = (
            f"llm={llm.__class__.__name__}, "
            f"embedder={embedder.__class__.__name__}, "
            f"vector={vector_store.__class__.__name__}, "
            f"reranker={reranker.__class__.__name__}, "
            f"parser={parser.__class__.__name__}"
        )
        return _pass("providers", details)
    except Exception as exc:
        return _fail("providers", f"provider check failed: {exc}")


async def run_preflight(
    *,
    expected_mode: str | None = None,
    probe_embedding: bool = False,
    probe_llm: bool = False,
) -> PreflightReport:
    """Run all preflight checks and return a consolidated report."""
    checks: list[CheckResult] = []

    env_check = check_environment(expected_mode=expected_mode)
    checks.append(env_check)

    # If env validation itself fails, dependency checks are likely noisy.
    if env_check.ok:
        checks.append(await check_database())
        checks.append(await check_redis())
        checks.append(
            await check_providers(
                probe_embedding=probe_embedding,
                probe_llm=probe_llm,
            )
        )

    mode = get_settings().app_mode
    ok = all(item.ok for item in checks)
    return PreflightReport(
        ok=ok,
        mode=mode,
        timestamp_utc=datetime.now(UTC).isoformat(),
        checks=checks,
    )

