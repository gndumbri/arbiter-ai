"""Global pytest fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.workers.celery_app import celery_app


@pytest.fixture(autouse=True)
def setup_celery():
    """Configure Celery to use memory broker for tests."""
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="memory://",
        task_always_eager=True,  # Run tasks synchronously in tests
        task_eager_propagates=True,
    )
    yield


@pytest.fixture
def db_session() -> MagicMock:
    """Mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(db_session: MagicMock) -> TestClient:
    """Synchronous TestClient with mocked DB."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
