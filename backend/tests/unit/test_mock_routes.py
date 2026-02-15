"""Tests for mock API routes (routes/mock_routes.py).

Validates that every mock endpoint:
  - Returns 200 (or appropriate status)
  - Returns valid response shapes matching real endpoint schemas
  - Works without DB, auth, or external APIs

WHY: Rather than patching `create_app()` (which has module-level imports),
we build a minimal FastAPI app directly from the mock routers. This tests
the routes in isolation — exactly how they'd behave in mock mode.

Run with: cd backend && uv run pytest tests/unit/test_mock_routes.py -v
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def mock_client():
    """Create a test client that mounts only mock routes.

    WHY: We skip create_app() and mount mock routers directly to avoid
    module-level imports of real route dependencies (database, auth, etc.).
    This mirrors what create_app() does when APP_MODE=mock.
    """
    from app.api.routes.mock_routes import api_router, router

    test_app = FastAPI(title="Arbiter AI - Mock Test")
    test_app.include_router(router)       # /health
    test_app.include_router(api_router)   # /api/v1/*

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac


# ─── Health ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_health(mock_client: AsyncClient):
    """Mock /health should return 200 with mode='mock'."""
    response = await mock_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    # WHY: The mode field reads from real settings (APP_MODE env var),
    # so we just verify it's present rather than asserting a specific value.
    assert "mode" in data


# ─── Users ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_get_current_user(mock_client: AsyncClient):
    """Mock /users/me should return the hardcoded pro user."""
    response = await mock_client.get("/api/v1/users/me")
    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    assert "email" in data
    assert data["tier"] == "PRO"


@pytest.mark.anyio
async def test_mock_update_user_profile(mock_client: AsyncClient):
    """Mock PATCH /users/me should update profile fields."""
    response = await mock_client.patch(
        "/api/v1/users/me",
        json={"name": "Updated Wizard", "default_ruling_privacy": "PUBLIC"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Wizard"
    assert data["default_ruling_privacy"] == "PUBLIC"


# ─── Sessions ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_sessions(mock_client: AsyncClient):
    """Mock /sessions should return a non-empty list."""
    response = await mock_client.get("/api/v1/sessions")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "game_name" in data[0]


@pytest.mark.anyio
async def test_mock_create_session(mock_client: AsyncClient):
    """Mock POST /sessions should return a new session."""
    response = await mock_client.post(
        "/api/v1/sessions",
        json={"game_name": "Test Game"},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["game_name"] == "Test Game"
    assert "id" in data


# ─── Judge ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_judge_query(mock_client: AsyncClient):
    """Mock POST /judge should return a verdict."""
    response = await mock_client.post(
        "/api/v1/judge",
        json={
            "session_id": "00000000-0000-4000-a000-000000000100",
            "query": "Can I attack twice in one turn?",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert "verdict" in data
    assert "confidence" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)


# ─── Catalog ──────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_catalog(mock_client: AsyncClient):
    """Mock /catalog/ should return a non-empty list."""
    response = await mock_client.get("/api/v1/catalog/")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "game_name" in data[0]
    assert "publisher_name" in data[0]


@pytest.mark.anyio
async def test_mock_catalog_search(mock_client: AsyncClient):
    """Mock /catalog/?search= should filter results."""
    response = await mock_client.get("/api/v1/catalog/?search=catan")
    assert response.status_code == 200

    data = response.json()
    assert all("catan" in e["game_name"].lower() for e in data)


@pytest.mark.anyio
async def test_mock_catalog_detail(mock_client: AsyncClient):
    """Mock /catalog/{slug} should return detail for known slug."""
    response = await mock_client.get("/api/v1/catalog/catan")
    assert response.status_code == 200

    data = response.json()
    assert data["game_slug"] == "catan"
    assert "chunk_count" in data


@pytest.mark.anyio
async def test_mock_catalog_detail_404(mock_client: AsyncClient):
    """Mock /catalog/{slug} should return 404 for unknown slug."""
    response = await mock_client.get("/api/v1/catalog/nonexistent-game")
    assert response.status_code == 404


# ─── Library ──────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_library(mock_client: AsyncClient):
    """Mock /library should return a non-empty list."""
    response = await mock_client.get("/api/v1/library")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.anyio
async def test_mock_add_to_library(mock_client: AsyncClient):
    """Mock POST /library should return a new library entry."""
    response = await mock_client.post(
        "/api/v1/library",
        json={"game_name": "Spirit Island"},
    )
    assert response.status_code == 201

    data = response.json()
    assert data["game_name"] == "Spirit Island"


@pytest.mark.anyio
async def test_mock_add_to_library_persists_in_list(mock_client: AsyncClient):
    game_name = f"Test Game {uuid.uuid4()}"
    create_resp = await mock_client.post(
        "/api/v1/library",
        json={"game_name": game_name},
    )
    assert create_resp.status_code == 201

    list_resp = await mock_client.get("/api/v1/library")
    assert list_resp.status_code == 200
    names = {entry["game_name"] for entry in list_resp.json()}
    assert game_name in names


# ─── Rulings ──────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_rulings(mock_client: AsyncClient):
    """Mock /rulings should return a non-empty list."""
    response = await mock_client.get("/api/v1/rulings")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "verdict_json" in data[0]


@pytest.mark.anyio
async def test_mock_list_public_and_party_rulings(mock_client: AsyncClient):
    """Mock /rulings/public and /rulings/party should filter by privacy."""
    public_resp = await mock_client.get("/api/v1/rulings/public")
    assert public_resp.status_code == 200
    assert all(r["privacy_level"] == "PUBLIC" for r in public_resp.json())

    party_resp = await mock_client.get("/api/v1/rulings/party")
    assert party_resp.status_code == 200
    assert all(r["privacy_level"] == "PARTY" for r in party_resp.json())


# ─── Billing ──────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_get_subscription(mock_client: AsyncClient):
    """Mock /billing/subscription should return active PRO."""
    response = await mock_client.get("/api/v1/billing/subscription")
    assert response.status_code == 200

    data = response.json()
    assert data["plan_tier"] == "PRO"
    assert data["status"] == "active"


@pytest.mark.anyio
async def test_mock_list_tiers(mock_client: AsyncClient):
    """Mock /billing/tiers should return FREE and PRO tiers."""
    response = await mock_client.get("/api/v1/billing/tiers")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    tier_names = [t["name"] for t in data]
    assert "FREE" in tier_names
    assert "PRO" in tier_names


# ─── Agents ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_agents(mock_client: AsyncClient):
    """Mock /agents should return a non-empty list."""
    response = await mock_client.get("/api/v1/agents")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "game_name" in data[0]


# ─── Parties ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_party_members_includes_name_and_email(mock_client: AsyncClient):
    response = await mock_client.get("/api/v1/parties/00000000-0000-4000-a000-000000000600/members")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "user_name" in data[0]
    assert "user_email" in data[0]


@pytest.mark.anyio
async def test_mock_create_party_and_invite_flow(mock_client: AsyncClient):
    """Mock party create + invite should return usable payloads."""
    create = await mock_client.post("/api/v1/parties", json={"name": "Audit Guild"})
    assert create.status_code == 201
    party = create.json()
    party_id = party["id"]

    invite = await mock_client.get(f"/api/v1/parties/{party_id}/invite")
    assert invite.status_code == 200
    assert "/invite/" in invite.json()["invite_url"]

    token = invite.json()["invite_url"].split("/invite/")[-1]
    join = await mock_client.post("/api/v1/parties/join-via-link", json={"token": token})
    # current mock user may already be owner/member; either is acceptable
    assert join.status_code in (201, 409)


# ─── Admin ────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_admin_endpoints(mock_client: AsyncClient):
    stats = await mock_client.get("/api/v1/admin/stats")
    assert stats.status_code == 200
    stats_data = stats.json()
    assert "total_users" in stats_data
    assert "total_sessions" in stats_data

    users = await mock_client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert isinstance(users.json(), list)

    publishers = await mock_client.get("/api/v1/admin/publishers")
    assert publishers.status_code == 200
    assert isinstance(publishers.json(), list)

    tiers = await mock_client.get("/api/v1/admin/tiers")
    assert tiers.status_code == 200
    tier_payload = tiers.json()
    assert isinstance(tier_payload, list)
    assert "id" in tier_payload[0]


# ─── Rulesets ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_list_rulesets(mock_client: AsyncClient):
    """Mock /rulesets should return a non-empty list."""
    response = await mock_client.get("/api/v1/rulesets")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]


@pytest.mark.anyio
async def test_mock_upload_ruleset_contract(mock_client: AsyncClient):
    """Mock upload should match real route path and response shape."""
    response = await mock_client.post("/api/v1/sessions/test-session/rulesets")
    assert response.status_code == 202

    data = response.json()
    assert "ruleset_id" in data
    assert data["status"] == "PROCESSING"


# ─── Environment ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mock_environment_info(mock_client: AsyncClient):
    """Mock /environment should return mode and features."""
    response = await mock_client.get("/api/v1/environment")
    assert response.status_code == 200

    data = response.json()
    assert "mode" in data
    assert "features" in data
