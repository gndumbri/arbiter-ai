"""Regression guards for GitHub deploy workflow service rollout coverage."""

from __future__ import annotations

from pathlib import Path


def _read_workflow() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    workflow = repo_root / ".github" / "workflows" / "deploy.yml"
    assert workflow.exists(), f"Missing workflow file: {workflow}"
    return workflow.read_text(encoding="utf-8")


def test_deploy_workflow_rolls_backend_worker_and_beat_together() -> None:
    text = _read_workflow()

    assert "--service $PROJECT_NAME-backend --force-new-deployment" in text
    assert "--service $PROJECT_NAME-worker --force-new-deployment" in text
    assert "--service $PROJECT_NAME-beat --force-new-deployment" in text


def test_deploy_workflow_waits_for_all_services_to_stabilize() -> None:
    text = _read_workflow()

    assert "$PROJECT_NAME-backend $PROJECT_NAME-frontend $PROJECT_NAME-worker $PROJECT_NAME-beat" in text


def test_deploy_workflow_supports_state_key_and_mode_overrides() -> None:
    text = _read_workflow()

    assert "tf_state_key" in text
    assert "force_unlock" in text
    assert "force_unlock_id" in text
    assert "DEFAULT_TF_STATE_KEY: prod/terraform.tfstate" in text
    assert "TF_STATE_KEY=\"${DEFAULT_TF_STATE_KEY}\"" in text
    assert "terraform init -backend-config=\"key=${{ steps.context.outputs.tf_state_key }}\"" in text
    assert "-var=\"environment=${{ steps.context.outputs.deploy_mode }}\"" in text
    assert "-var=\"app_mode=${{ steps.context.outputs.deploy_mode }}\"" in text


def test_deploy_workflow_loads_environment_tfvars_when_present() -> None:
    text = _read_workflow()

    assert "TF_VARS_FILE=\"environments/${DEPLOY_MODE}.tfvars\"" in text
    assert "PLAN_ARGS+=(\"-var-file=${{ steps.context.outputs.tf_vars_file }}\")" in text


def test_deploy_workflow_imports_existing_ecs_services_before_plan() -> None:
    text = _read_workflow()

    assert 'terraform import "${IMPORT_ARGS[@]}" -lock-timeout=10m "aws_ecs_service.${svc}" "${PROJECT_NAME}-cluster/${PROJECT_NAME}-${svc}" || true' in text


def test_deploy_workflow_import_step_has_required_tf_vars() -> None:
    text = _read_workflow()

    assert "TF_VAR_secrets_manager_arn: ${{ secrets.SECRETS_MANAGER_ARN }}" in text
    assert "TF_VAR_db_password: ${{ secrets.DB_PASSWORD }}" in text
    assert "TF_VAR_environment: ${{ steps.context.outputs.deploy_mode }}" in text
    assert "IMPORT_ARGS+=(\"-var-file=${{ steps.context.outputs.tf_vars_file }}\")" in text


def test_deploy_workflow_fails_fast_when_required_secrets_missing() -> None:
    text = _read_workflow()

    assert "Validate required Terraform secrets" in text
    assert "Missing required GitHub secret: SECRETS_MANAGER_ARN" in text
    assert "Missing required GitHub secret: DB_PASSWORD" in text


def test_deploy_workflow_runs_infra_prebuild_checks_before_builds() -> None:
    text = _read_workflow()

    assert "infra-prebuild-check:" in text
    assert "python3 infra/scripts/check_infra_inventory.py --check" in text
    assert "terraform -chdir=infra/terraform validate" in text
    assert "needs: [changes, infra-prebuild-check]" in text


def test_deploy_workflow_serializes_deploy_runs_and_handles_tf_locks() -> None:
    text = _read_workflow()

    assert "concurrency:" in text
    assert "group: deploy-${{ github.workflow }}-${{ github.ref }}" in text
    assert "-lock-timeout=10m" in text
    assert "terraform force-unlock -force" in text
    assert "Validate production tfvars profile" in text
    assert "Production deploy requires infra/terraform/environments/production.tfvars" in text
    assert "Prune unmanaged SES domain state (production)" in text
    assert "terraform state rm 'aws_ses_domain_identity.main[0]'" in text
    assert "Validate manual force-unlock inputs" in text
    assert "force_unlock=true requires force_unlock_id to be set." in text
    assert "Optional manual force-unlock" in text
    assert "github.event.inputs.force_unlock == 'true'" in text
