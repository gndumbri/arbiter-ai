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
    assert '{ name = "CATALOG_SYNC_ENABLED", value = tostring(var.catalog_sync_enabled) }' in text
    assert '{ name = "OPEN_RULES_SYNC_ENABLED", value = tostring(var.open_rules_sync_enabled) }' in text


def test_terraform_backend_excludes_unused_provider_secret_mappings() -> None:
    text = _read_tf("infra/terraform/ecs.tf")

    assert ":PINECONE_API_KEY::" not in text
    assert ":OPENAI_API_KEY::" not in text
    assert ":ANTHROPIC_API_KEY::" not in text
    assert ":COHERE_API_KEY::" not in text


def test_terraform_frontend_uses_frontend_database_secret_and_api_base() -> None:
    text = _read_tf("infra/terraform/ecs.tf")
    vars_text = _read_tf("infra/terraform/variables.tf")

    assert '{ name = "APP_MODE", value = var.app_mode }' in text
    assert '{ name = "NEXTAUTH_URL", value = local.resolved_frontend_nextauth_url }' in text
    assert '{ name = "NEXT_PUBLIC_API_URL", value = var.next_public_api_url }' in text
    assert '{ name = "NODE_OPTIONS", value = var.frontend_node_options }' in text
    assert (
        '{ name = "SANDBOX_EMAIL_BYPASS_ENABLED", value = var.app_mode == "sandbox" '
        '? tostring(var.sandbox_email_bypass_enabled) : "false" }'
    ) in text
    assert '{ name = "EMAIL_PROVIDER", value = lower(var.email_provider) }' in text
    assert ':FRONTEND_DATABASE_URL::' in text
    assert ':EMAIL_SERVER::' in text
    assert ':BREVO_API_KEY::' in text
    assert 'variable "email_provider"' in vars_text
    assert 'variable "frontend_node_options"' in vars_text
    assert 'variable "sandbox_email_bypass_enabled"' in vars_text


def test_terraform_provisions_worker_and_beat_services() -> None:
    text = _read_tf("infra/terraform/ecs.tf")

    assert 'resource "aws_ecs_task_definition" "worker"' in text
    assert 'resource "aws_ecs_task_definition" "beat"' in text
    assert 'resource "aws_ecs_service" "worker"' in text
    assert 'resource "aws_ecs_service" "beat"' in text
    assert 'command   = ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]' in text
    assert 'command   = ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]' in text


def test_terraform_mounts_shared_efs_volume_for_upload_handoff() -> None:
    ecs_text = _read_tf("infra/terraform/ecs.tf")
    efs_text = _read_tf("infra/terraform/efs.tf")

    assert 'resource "aws_efs_file_system" "uploads"' in efs_text
    assert 'resource "aws_efs_access_point" "uploads"' in efs_text
    assert 'containerPath = var.uploads_dir' in ecs_text
    assert 'file_system_id     = local.resolved_efs_file_system_id' in ecs_text
    assert 'shared_uploads_enabled' in ecs_text


def test_terraform_task_role_has_bedrock_permissions() -> None:
    text = _read_tf("infra/terraform/iam.tf")

    assert "resource \"aws_iam_role_policy\" \"ecs_task_bedrock\"" in text
    assert "\"bedrock:InvokeModel\"" in text
    assert "\"bedrock:InvokeModelWithResponseStream\"" in text


def test_terraform_declares_optional_ses_domain_and_gates_ses_resources() -> None:
    vars_text = _read_tf("infra/terraform/variables.tf")
    ses_text = _read_tf("infra/terraform/ses.tf")

    assert 'variable "ses_domain"' in vars_text
    assert 'default     = ""' in vars_text
    assert 'trimspace(var.ses_domain) != "" ? 1 : 0' in ses_text


def test_terraform_github_actions_role_includes_efs_permissions() -> None:
    text = _read_tf("infra/terraform/iam.tf")

    assert "\"elasticfilesystem:CreateFileSystem\"" in text
    assert "\"elasticfilesystem:CreateMountTarget\"" in text
    assert "\"elasticfilesystem:CreateAccessPoint\"" in text


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


def test_terraform_supports_existing_infra_deploy_mode_defaults() -> None:
    vars_text = _read_tf("infra/terraform/variables.tf")
    vpc_text = _read_tf("infra/terraform/vpc.tf")
    iam_text = _read_tf("infra/terraform/iam.tf")
    cloudwatch_text = _read_tf("infra/terraform/cloudwatch.tf")
    sg_text = _read_tf("infra/terraform/security_groups.tf")
    alb_text = _read_tf("infra/terraform/alb.tf")

    assert 'variable "create_networking"' in vars_text
    assert 'variable "create_service_security_groups"' in vars_text
    assert 'variable "create_alb_resources"' in vars_text
    assert 'variable "create_ecs_task_roles"' in vars_text
    assert 'variable "create_github_actions_iam"' in vars_text
    assert 'variable "create_cloudwatch_log_groups"' in vars_text
    assert 'variable "create_efs_resources"' in vars_text
    assert 'variable "create_data_services"' in vars_text
    assert 'default     = false' in vars_text
    assert 'data "aws_vpcs" "existing"' in vpc_text
    assert 'data "aws_iam_role" "existing_ecs_task_execution"' in iam_text
    assert 'data "aws_security_group" "existing_alb"' in sg_text
    assert 'data "aws_lb_target_group" "existing_backend"' in alb_text
    assert 'local.backend_log_group_name' in cloudwatch_text


def test_terraform_commits_full_sandbox_bootstrap_profile() -> None:
    sandbox_vars = _read_tf("infra/terraform/environments/sandbox.tfvars")

    assert 'environment = "sandbox"' in sandbox_vars
    assert "create_networking              = true" in sandbox_vars
    assert "create_service_security_groups = true" in sandbox_vars
    assert "create_alb_resources           = true" in sandbox_vars
    assert "create_ecs_task_roles          = true" in sandbox_vars
    assert "create_cloudwatch_log_groups   = true" in sandbox_vars
    assert "create_data_services           = true" in sandbox_vars
    assert "create_efs_resources           = true" in sandbox_vars
    assert "catalog_sync_enabled      = true" in sandbox_vars


def test_terraform_commits_safe_production_profile() -> None:
    production_vars = _read_tf("infra/terraform/environments/production.tfvars")

    assert 'environment = "production"' in production_vars
    assert "create_networking              = true" in production_vars
    assert "create_service_security_groups = true" in production_vars
    assert "create_alb_resources           = true" in production_vars
    assert "create_ecs_task_roles          = true" in production_vars
    assert "create_cloudwatch_log_groups   = true" in production_vars
    assert "create_data_services           = true" in production_vars
    assert "create_github_actions_iam = true" in production_vars
    assert "catalog_sync_enabled        = true" in production_vars
    assert "open_rules_sync_enabled     = true" in production_vars
    assert 'ses_domain = ""' in production_vars
