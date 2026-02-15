"""Regression tests for frontend ECS task definition template."""

from __future__ import annotations

import json
from pathlib import Path


def _load_frontend_taskdef() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    taskdef_path = repo_root / "infra" / "ecs" / "frontend-task-definition.json"
    assert taskdef_path.exists(), f"Missing task definition template: {taskdef_path}"
    return json.loads(taskdef_path.read_text(encoding="utf-8"))


def test_frontend_taskdef_includes_expected_runtime_secrets() -> None:
    taskdef = _load_frontend_taskdef()
    secrets = taskdef["containerDefinitions"][0].get("secrets", [])
    secret_names = {item["name"] for item in secrets}

    required = {
        "AUTH_SECRET",
        "DATABASE_URL",
    }
    assert required.issubset(secret_names)


def test_frontend_taskdef_avoids_irrelevant_llm_keys() -> None:
    taskdef = _load_frontend_taskdef()
    secrets = taskdef["containerDefinitions"][0].get("secrets", [])
    secret_names = {item["name"] for item in secrets}

    assert "OPENAI_API_KEY" not in secret_names
    assert "ANTHROPIC_API_KEY" not in secret_names
    assert "PINECONE_API_KEY" not in secret_names


def test_frontend_taskdef_sets_app_mode() -> None:
    taskdef = _load_frontend_taskdef()
    environment = taskdef["containerDefinitions"][0].get("environment", [])
    env_map = {item["name"]: item["value"] for item in environment}

    assert env_map.get("APP_MODE") in {"sandbox", "production"}


def test_frontend_taskdef_includes_api_base_and_nextauth_url() -> None:
    taskdef = _load_frontend_taskdef()
    environment = taskdef["containerDefinitions"][0].get("environment", [])
    env_map = {item["name"]: item["value"] for item in environment}

    assert env_map.get("NEXT_PUBLIC_API_URL")
    assert env_map.get("NEXTAUTH_URL")
    assert "AUTH_URL" not in env_map


def test_frontend_taskdef_healthcheck_does_not_require_curl() -> None:
    taskdef = _load_frontend_taskdef()
    health = taskdef["containerDefinitions"][0].get("healthCheck", {})
    command = " ".join(health.get("command", []))

    assert "curl" not in command
    assert "fetch('http://localhost:3000/')" in command
