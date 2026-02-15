"""Regression tests for CORS behavior on middleware short-circuit responses."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import ip_rate_limit


class _AlwaysLimitedRedis:
    """Minimal async Redis stub that always exceeds the rate limit."""

    async def incr(self, key: str) -> int:  # noqa: ARG002
        return ip_rate_limit.IP_RATE_LIMIT + 1

    async def expire(self, key: str, ttl: int) -> bool:  # noqa: ARG002
        return True

    async def ttl(self, key: str) -> int:  # noqa: ARG002
        return 30


def test_cors_header_present_on_ip_rate_limit_response(
    client: TestClient,
    monkeypatch,
) -> None:
    """429 responses from IP middleware must still include CORS headers."""
    monkeypatch.setattr(ip_rate_limit, "_ip_redis", _AlwaysLimitedRedis())

    response = client.get(
        "/api/v1/sessions",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
