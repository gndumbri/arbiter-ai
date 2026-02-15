"""Regression guards for Terraform ECS/IAM AWS readiness wiring."""

from __future__ import annotations

from pathlib import Path


def _read_tf(relative_path: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / relative_path
    assert path.exists(), f"Missing terraform file: {path}"
    return path.read_text(encoding="utf-8")


def test_terraform_backend_uses_bedrock_pgvector_and_core_runtime_env() -> None:
    text = _read_tf("infra/terraform/ecs.tf")

    assert '{ name = "LLM_PROVIDER", value = "bedrock" }' in text
    assert '{ name = "EMBEDDING_PROVIDER", value = "bedrock" }' in text
    assert '{ name = "VECTOR_STORE_PROVIDER", value = "pgvector" }' in text
    assert '{ name = "ALLOWED_ORIGINS", value = local.resolved_allowed_origins }' in text
    assert '{ name = "APP_BASE_URL", value = local.resolved_app_base_url }' in text
    assert '{ name = "TRUSTED_PROXY_HOPS", value = tostring(var.trusted_proxy_hops) }' in text


def test_terraform_backend_excludes_unused_provider_secret_mappings() -> None:
    text = _read_tf("infra/terraform/ecs.tf")

    assert ":PINECONE_API_KEY::" not in text
    assert ":OPENAI_API_KEY::" not in text
    assert ":ANTHROPIC_API_KEY::" not in text
    assert ":COHERE_API_KEY::" not in text


def test_terraform_frontend_uses_frontend_database_secret_and_api_base() -> None:
    text = _read_tf("infra/terraform/ecs.tf")

    assert '{ name = "APP_MODE", value = var.app_mode }' in text
    assert '{ name = "NEXTAUTH_URL", value = local.resolved_frontend_nextauth_url }' in text
    assert '{ name = "NEXT_PUBLIC_API_URL", value = var.next_public_api_url }' in text
    assert ':FRONTEND_DATABASE_URL::' in text
    assert ':BREVO_API_KEY::' in text


def test_terraform_task_role_has_bedrock_permissions() -> None:
    text = _read_tf("infra/terraform/iam.tf")

    assert "resource \"aws_iam_role_policy\" \"ecs_task_bedrock\"" in text
    assert "\"bedrock:InvokeModel\"" in text
    assert "\"bedrock:InvokeModelWithResponseStream\"" in text


def test_terraform_alb_supports_optional_https_listener() -> None:
    alb_text = _read_tf("infra/terraform/alb.tf")
    vars_text = _read_tf("infra/terraform/variables.tf")

    assert "variable \"alb_certificate_arn\"" in vars_text
    assert "resource \"aws_lb_listener\" \"https\"" in alb_text
    assert "HTTP_301" in alb_text


def test_terraform_uses_production_environment_label_consistently_for_rds_snapshot_logic() -> None:
    vars_text = _read_tf("infra/terraform/variables.tf")
    rds_text = _read_tf("infra/terraform/rds.tf")

    assert 'default     = "production"' in vars_text
    assert 'skip_final_snapshot = var.environment != "production"' in rds_text
    assert 'var.environment == "production"' in rds_text
