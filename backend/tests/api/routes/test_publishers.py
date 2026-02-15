
import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.models.tables import OfficialRuleset, Publisher


def test_create_publisher(client: TestClient, db_session: MagicMock):
    # Mock DB behavior: check for existing slug returns None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute.return_value = mock_result

    db_session.commit = AsyncMock()

    # Simulate valid ID assignment on refresh
    async def mock_refresh(instance):
        instance.id = uuid.uuid4()
        instance.verified = False
        return None
    db_session.refresh = AsyncMock(side_effect=mock_refresh)

    response = client.post(
        "/api/v1/publishers/",
        json={
            "name": "Acme Games",
            "slug": "acme-games",
            "contact_email": "contact@acme.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Games"
    assert data["slug"] == "acme-games"
    assert "id" in data
    assert data["verified"] is False

def test_create_duplicate_publisher(client: TestClient, db_session: MagicMock):
    # Mock DB behavior: check for existing slug returns a Publisher
    existing_pub = Publisher(id=uuid.uuid4(), name="Existing", slug="duplicate")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_pub
    db_session.execute.return_value = mock_result

    response = client.post(
        "/api/v1/publishers/",
        json={
            "name": "Duplicate Games 2",
            "slug": "duplicate",
            "contact_email": "dup@test.com",
        },
    )
    assert response.status_code == 409

def test_create_official_ruleset(client: TestClient, db_session: MagicMock):
    # WHY: Publisher routes now verify X-Publisher-Key header against
    # a SHA-256 hash stored in the publisher record. The test must
    # provide a valid key and matching hash.
    import hashlib
    test_key = "arb_test_key_123"
    test_key_hash = hashlib.sha256(test_key.encode()).hexdigest()

    # Mock db.get(Publisher) -> returns publisher with key hash (async)
    mock_pub = Publisher(
        id=uuid.uuid4(),
        name="Test Pub",
        slug="test-pub",
        api_key_hash=test_key_hash,
    )
    db_session.get = AsyncMock(return_value=mock_pub)

    # Mock db.execute(check_slug) -> returns None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db_session.execute = AsyncMock(return_value=mock_result)

    db_session.commit = AsyncMock()

    # Simulate valid ID assignment on refresh
    async def mock_refresh(instance):
        instance.id = uuid.uuid4()
        instance.chunk_count = 0
        instance.status = "CREATED"
        return None
    db_session.refresh = AsyncMock(side_effect=mock_refresh)

    response = client.post(
        f"/api/v1/publishers/{mock_pub.id}/games",
        json={
            "game_name": "Test Game",
            "game_slug": "test-game",
            "version": "1.0",
            "pinecone_namespace": "test-game-ns",
        },
        headers={"X-Publisher-Key": test_key},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["game_name"] == "Test Game"
    assert data["status"] == "CREATED"

def test_catalog(client: TestClient, db_session: MagicMock):
    # Mock db.execute returning a list of rulesets with pre-loaded publisher
    mock_pub = Publisher(id="123e4567-e89b-12d3-a456-426614174000", name="Test Pub", slug="test-pub")
    mock_ruleset = OfficialRuleset(
        id="123e4567-e89b-12d3-a456-426614174001",
        game_name="Test Game",
        game_slug="test-game",
        version="1.0",
        status="READY",
        publisher=mock_pub
    )

    mock_result = MagicMock()
    # scalars().all() -> list
    mock_result.scalars.return_value.all.return_value = [mock_ruleset]
    db_session.execute = AsyncMock(return_value=mock_result)

    response = client.get("/api/v1/catalog/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["game_slug"] == "test-game"
    assert data[0]["publisher_name"] == "Test Pub"
