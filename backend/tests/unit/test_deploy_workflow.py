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
    assert "terraform init -backend-config=\"key=${{ steps.context.outputs.tf_state_key }}\"" in text
    assert "-var=\"environment=${{ steps.context.outputs.deploy_mode }}\"" in text
    assert "-var=\"app_mode=${{ steps.context.outputs.deploy_mode }}\"" in text


def test_deploy_workflow_loads_environment_tfvars_when_present() -> None:
    text = _read_workflow()

    assert "TF_VARS_FILE=\"environments/${DEPLOY_MODE}.tfvars\"" in text
    assert "PLAN_ARGS+=(\"-var-file=${{ steps.context.outputs.tf_vars_file }}\")" in text
