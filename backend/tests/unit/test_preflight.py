"""Unit tests for deployment preflight checks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.preflight import CheckResult, check_environment, run_preflight


def _result(name: str, ok: bool, detail: str) -> CheckResult:
    return CheckResult(name=name, ok=ok, detail=detail)


@patch("app.core.preflight.get_settings")
@patch("app.core.preflight.validate_environment")
def test_check_environment_passes_with_expected_mode(mock_validate, mock_get_settings) -> None:
    mock_get_settings.return_value = SimpleNamespace(app_mode="sandbox", app_env="staging")

    result = check_environment(expected_mode="sandbox")

    assert result.ok is True
    assert result.name == "environment"
    assert "mode=sandbox" in result.detail
    mock_validate.assert_called_once()


@patch("app.core.preflight.get_settings")
@patch("app.core.preflight.validate_environment")
def test_check_environment_fails_on_mode_mismatch(mock_validate, mock_get_settings) -> None:
    mock_get_settings.return_value = SimpleNamespace(app_mode="sandbox", app_env="staging")

    result = check_environment(expected_mode="production")

    assert result.ok is False
    assert "expected 'production'" in result.detail
    mock_validate.assert_called_once()


@patch("app.core.preflight.validate_environment")
def test_check_environment_surfaces_validation_error(mock_validate) -> None:
    mock_validate.side_effect = RuntimeError("bad env")

    result = check_environment(expected_mode="sandbox")

    assert result.ok is False
    assert "validation failed" in result.detail


@pytest.mark.asyncio
@patch("app.core.preflight.get_settings")
@patch("app.core.preflight.check_providers", new_callable=AsyncMock)
@patch("app.core.preflight.check_redis", new_callable=AsyncMock)
@patch("app.core.preflight.check_database", new_callable=AsyncMock)
@patch("app.core.preflight.check_environment")
async def test_run_preflight_skips_dependency_checks_when_env_fails(
    mock_env,
    mock_db,
    mock_redis,
    mock_providers,
    mock_get_settings,
) -> None:
    mock_env.return_value = _result("environment", False, "APP_MODE mismatch")
    mock_get_settings.return_value = SimpleNamespace(app_mode="sandbox")

    report = await run_preflight(expected_mode="production")

    assert report.ok is False
    assert len(report.checks) == 1
    assert report.checks[0].name == "environment"
    mock_db.assert_not_awaited()
    mock_redis.assert_not_awaited()
    mock_providers.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.core.preflight.get_settings")
@patch("app.core.preflight.check_providers", new_callable=AsyncMock)
@patch("app.core.preflight.check_redis", new_callable=AsyncMock)
@patch("app.core.preflight.check_database", new_callable=AsyncMock)
@patch("app.core.preflight.check_environment")
async def test_run_preflight_passes_when_all_checks_pass(
    mock_env,
    mock_db,
    mock_redis,
    mock_providers,
    mock_get_settings,
) -> None:
    mock_env.return_value = _result("environment", True, "validated")
    mock_db.return_value = _result("database", True, "connection ok")
    mock_redis.return_value = _result("redis", True, "ping ok")
    mock_providers.return_value = _result("providers", True, "providers ok")
    mock_get_settings.return_value = SimpleNamespace(app_mode="production")

    report = await run_preflight(
        expected_mode="production",
        probe_embedding=True,
        probe_llm=True,
    )

    assert report.ok is True
    assert [check.name for check in report.checks] == [
        "environment",
        "database",
        "redis",
        "providers",
    ]
    mock_providers.assert_awaited_once_with(
        probe_embedding=True,
        probe_llm=True,
    )


@pytest.mark.asyncio
@patch("app.core.preflight.get_settings")
@patch("app.core.preflight.check_providers", new_callable=AsyncMock)
@patch("app.core.preflight.check_redis", new_callable=AsyncMock)
@patch("app.core.preflight.check_database", new_callable=AsyncMock)
@patch("app.core.preflight.check_environment")
async def test_run_preflight_fails_when_dependency_check_fails(
    mock_env,
    mock_db,
    mock_redis,
    mock_providers,
    mock_get_settings,
) -> None:
    mock_env.return_value = _result("environment", True, "validated")
    mock_db.return_value = _result("database", False, "connection failed")
    mock_redis.return_value = _result("redis", True, "ping ok")
    mock_providers.return_value = _result("providers", True, "providers ok")
    mock_get_settings.return_value = SimpleNamespace(app_mode="sandbox")

    report = await run_preflight(expected_mode="sandbox")

    assert report.ok is False
    assert any(item.name == "database" and item.ok is False for item in report.checks)
