"""Tests for application configuration."""

from __future__ import annotations

from app.config import Settings, get_settings


def test_default_settings():
    """Settings should have sensible defaults."""
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.is_production is False
    assert settings.pinecone_index_name == "arbiter-rules"


def test_production_detection():
    """is_production should be True when app_env is 'production'."""
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert settings.is_production is True


def test_get_settings_returns_singleton():
    """get_settings should return the same instance on repeated calls."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
