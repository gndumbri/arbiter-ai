"""Tests for application configuration."""

from __future__ import annotations

from app.config import Settings, get_settings


def test_default_settings():
    """Settings should have sensible defaults."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
    )
    assert settings.app_env == "development"
    assert settings.is_production is False
    assert settings.llm_provider == "bedrock"
    assert settings.embedding_provider == "bedrock"
    assert settings.reranker_provider == "flashrank"
    assert settings.vector_store_provider == "pgvector"


def test_production_detection():
    """is_production should be True when app_env is 'production'."""
    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert settings.is_production is True


def test_allowed_origins_list_parsing():
    """ALLOWED_ORIGINS should parse into a trimmed list."""
    settings = Settings(
        _env_file=None,
        allowed_origins="https://app.example.com, https://admin.example.com ",
        app_base_url="https://app.example.com/",
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert settings.allowed_origins_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.normalized_app_base_url == "https://app.example.com"


def test_allowed_origins_fallback_to_app_base_url():
    """When ALLOWED_ORIGINS is empty, fallback to APP_BASE_URL."""
    settings = Settings(
        _env_file=None,
        allowed_origins="",
        app_base_url="https://app.example.com",
        database_url="postgresql+asyncpg://test:test@localhost/test",
    )
    assert settings.allowed_origins_list == ["https://app.example.com"]


def test_get_settings_returns_singleton():
    """get_settings should return the same instance on repeated calls."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
