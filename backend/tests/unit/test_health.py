"""Tests for the health check endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.anyio
async def test_health_returns_200(client: AsyncClient):
    """Health endpoint should return 200 with status fields."""
    # Mock DB and Redis to avoid needing real connections in unit tests
    with (
        patch("app.api.routes.health.DBSession", new_callable=AsyncMock),
        patch("app.api.routes.health.RedisDep", new_callable=AsyncMock),
    ):
        response = await client.get("/health")

    # The endpoint may not connect to real services, but should not crash
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "version" in data


@pytest.mark.anyio
async def test_health_response_structure(client: AsyncClient):
    """Health response should match the expected schema."""
    response = await client.get("/health")
    data = response.json()

    assert isinstance(data["status"], str)
    assert data["status"] in ("healthy", "degraded")
    assert isinstance(data["version"], str)
