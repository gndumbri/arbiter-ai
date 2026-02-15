"""Tests for the environment manager (core/environment.py).

Validates mode detection, startup validation, and environment info
across all three tiers (mock, sandbox, production).

Run with: cd backend && uv run pytest tests/unit/test_environment.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.environment import (
    MODE_MOCK,
    MODE_PRODUCTION,
    MODE_SANDBOX,
    VALID_MODES,
    EnvironmentInfo,
    get_environment_info,
    to_dict,
    validate_environment,
)


class TestEnvironmentInfo:
    """Tests for the EnvironmentInfo dataclass and get_environment_info()."""

    def test_valid_modes_contains_all_three(self):
        """All three modes should be in the valid set."""
        assert MODE_MOCK in VALID_MODES
        assert MODE_SANDBOX in VALID_MODES
        assert MODE_PRODUCTION in VALID_MODES
        assert len(VALID_MODES) == 3

    @patch("app.core.environment.get_settings")
    def test_get_environment_info_mock_mode(self, mock_settings):
        """Mock mode should enable mock_data and auth_bypass features."""
        mock_settings.return_value.app_mode = "mock"
        mock_settings.return_value.is_mock = True
        mock_settings.return_value.is_sandbox = False
        mock_settings.return_value.app_env = "development"

        info = get_environment_info()

        assert info.mode == "mock"
        assert info.features["mock_data"] is True
        assert info.features["auth_bypass"] is True
        assert info.features["debug_tools"] is True
        assert info.features["live_billing"] is False

    @patch("app.core.environment.get_settings")
    def test_get_environment_info_sandbox_mode(self, mock_settings):
        """Sandbox mode should enable sandbox_billing and debug_tools."""
        mock_settings.return_value.app_mode = "sandbox"
        mock_settings.return_value.is_mock = False
        mock_settings.return_value.is_sandbox = True
        mock_settings.return_value.app_env = "development"

        info = get_environment_info()

        assert info.mode == "sandbox"
        assert info.features["sandbox_billing"] is True
        assert info.features["mock_data"] is False
        assert info.features["auth_bypass"] is False
        assert info.features["debug_tools"] is True

    @patch("app.core.environment.get_settings")
    def test_get_environment_info_production_mode(self, mock_settings):
        """Production mode should disable debug_tools and enable live_billing."""
        mock_settings.return_value.app_mode = "production"
        mock_settings.return_value.is_mock = False
        mock_settings.return_value.is_sandbox = False
        mock_settings.return_value.app_env = "production"

        info = get_environment_info()

        assert info.mode == "production"
        assert info.features["live_billing"] is True
        assert info.features["debug_tools"] is False
        assert info.features["mock_data"] is False

    def test_to_dict_serialization(self):
        """to_dict() should produce a JSON-safe dict."""
        info = EnvironmentInfo(
            mode="mock",
            app_env="development",
            version="0.1.0",
            features={"mock_data": True},
        )
        result = to_dict(info)

        assert result["mode"] == "mock"
        assert result["version"] == "0.1.0"
        assert result["features"]["mock_data"] is True


class TestValidateEnvironment:
    """Tests for the validate_environment() startup check."""

    @patch("app.core.environment.get_settings")
    def test_invalid_mode_raises_error(self, mock_settings):
        """An unrecognized APP_MODE should raise ValueError."""
        mock_settings.return_value.app_mode = "invalid_tier"
        mock_settings.return_value.allowed_origins_list = ["http://localhost:3000"]
        mock_settings.return_value.normalized_app_base_url = "http://localhost:3000"

        with pytest.raises(ValueError, match="Invalid APP_MODE"):
            validate_environment()

    @patch("app.core.environment.get_settings")
    def test_mock_mode_validates_ok(self, mock_settings):
        """Mock mode should validate without errors."""
        mock_settings.return_value.app_mode = "mock"
        mock_settings.return_value.app_env = "development"
        mock_settings.return_value.allowed_origins_list = ["http://localhost:3000"]
        mock_settings.return_value.normalized_app_base_url = "http://localhost:3000"

        # Should not raise
        validate_environment()

    @patch("app.core.environment.get_settings")
    def test_sandbox_mode_validates_ok(self, mock_settings):
        """Sandbox mode should validate (warnings are logged, not raised)."""
        mock_settings.return_value.app_mode = "sandbox"
        mock_settings.return_value.app_env = "development"
        mock_settings.return_value.allowed_origins_list = ["http://localhost:3000"]
        mock_settings.return_value.normalized_app_base_url = "http://localhost:3000"
        mock_settings.return_value.stripe_secret_key = ""
        mock_settings.return_value.llm_provider = "bedrock"
        mock_settings.return_value.embedding_provider = "bedrock"
        mock_settings.return_value.aws_region = "us-east-1"

        # Should not raise (warnings are logged)
        validate_environment()

    @patch("app.core.environment.get_settings")
    def test_production_mode_missing_keys_raises(self, mock_settings):
        """Production mode should fail fast when required keys are missing."""
        mock_settings.return_value.app_mode = "production"
        mock_settings.return_value.app_env = "production"
        mock_settings.return_value.allowed_origins_list = ["https://app.example.com"]
        mock_settings.return_value.normalized_app_base_url = "https://app.example.com"
        mock_settings.return_value.stripe_secret_key = ""
        mock_settings.return_value.nextauth_secret = ""
        mock_settings.return_value.llm_provider = "bedrock"
        mock_settings.return_value.embedding_provider = "bedrock"
        mock_settings.return_value.aws_region = "us-east-1"

        with pytest.raises(RuntimeError, match="Production mode requires"):
            validate_environment()

    @patch("app.core.environment.get_settings")
    def test_production_wildcard_origin_rejected(self, mock_settings):
        """Production must not allow wildcard CORS origins."""
        mock_settings.return_value.app_mode = "production"
        mock_settings.return_value.app_env = "production"
        mock_settings.return_value.allowed_origins_list = ["*"]
        mock_settings.return_value.normalized_app_base_url = "https://app.example.com"

        with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS cannot contain"):
            validate_environment()

    @patch("app.core.environment.get_settings")
    def test_invalid_app_base_url_rejected(self, mock_settings):
        """APP_BASE_URL should be a full http(s) URL."""
        mock_settings.return_value.app_mode = "sandbox"
        mock_settings.return_value.app_env = "development"
        mock_settings.return_value.allowed_origins_list = ["http://localhost:3000"]
        mock_settings.return_value.normalized_app_base_url = "localhost:3000"

        with pytest.raises(RuntimeError, match="APP_BASE_URL must be a full"):
            validate_environment()
