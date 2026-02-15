"""Regression tests for ECS task definition templates.

These tests prevent config drift that can break AWS task startup before
application code runs (e.g., missing/unneeded secret JSON keys).
"""

from __future__ import annotations

import json
from pathlib import Path


def _load_backend_taskdef() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    taskdef_path = repo_root / "infra" / "ecs" / "backend-task-definition.json"
    assert taskdef_path.exists(), f"Missing task definition template: {taskdef_path}"
    return json.loads(taskdef_path.read_text(encoding="utf-8"))


def test_backend_taskdef_excludes_unused_provider_secrets() -> None:
    taskdef = _load_backend_taskdef()
    secrets = taskdef["containerDefinitions"][0].get("secrets", [])
    secret_names = {item["name"] for item in secrets}

    # Regression guard: these caused ECS ResourceInitializationError when absent.
    assert "PINECONE_API_KEY" not in secret_names
    assert "OPENAI_API_KEY" not in secret_names
    assert "COHERE_API_KEY" not in secret_names


def test_backend_taskdef_includes_required_runtime_secrets() -> None:
    taskdef = _load_backend_taskdef()
    secrets = taskdef["containerDefinitions"][0].get("secrets", [])
    secret_names = {item["name"] for item in secrets}

    required = {
        "DATABASE_URL",
        "REDIS_URL",
        "NEXTAUTH_SECRET",
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_ID",
    }
    assert required.issubset(secret_names)


def test_backend_taskdef_uses_bedrock_pgvector_defaults() -> None:
    taskdef = _load_backend_taskdef()
    environment = taskdef["containerDefinitions"][0].get("environment", [])
    env_map = {item["name"]: item["value"] for item in environment}

    assert env_map.get("LLM_PROVIDER") == "bedrock"
    assert env_map.get("EMBEDDING_PROVIDER") == "bedrock"
    assert env_map.get("VECTOR_STORE_PROVIDER") == "pgvector"
    assert env_map.get("RERANKER_PROVIDER") == "flashrank"


def test_backend_taskdef_enables_periodic_catalog_and_rules_sync() -> None:
    taskdef = _load_backend_taskdef()
    environment = taskdef["containerDefinitions"][0].get("environment", [])
    env_map = {item["name"]: item["value"] for item in environment}

    assert env_map.get("CATALOG_SYNC_ENABLED") == "true"
    assert env_map.get("OPEN_RULES_SYNC_ENABLED") == "true"
    assert env_map.get("CATALOG_RANKED_GAME_LIMIT") == "1000"
    assert env_map.get("OPEN_RULES_MAX_DOCUMENTS") == "20"
