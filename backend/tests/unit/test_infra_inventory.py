"""Regression guards for infra inventory documentation drift."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_infra_inventory_document_exists_and_lists_core_folders() -> None:
    repo_root = _repo_root()
    inventory = repo_root / "infra" / "INFRA_INVENTORY.md"
    permission_map = repo_root / "infra" / "TERRAFORM_PERMISSION_MAP.md"
    assert inventory.exists(), f"Missing infra inventory doc: {inventory}"
    assert permission_map.exists(), f"Missing Terraform permission map doc: {permission_map}"
    text = inventory.read_text(encoding="utf-8")
    permission_text = permission_map.read_text(encoding="utf-8")

    assert "`infra/ecs`" in text
    assert "`infra/scripts`" in text
    assert "`infra/terraform`" in text
    assert "`infra/terraform/environments`" in text
    assert "`infra/TERRAFORM_PERMISSION_MAP.md`" in text
    assert "Module-by-Module AWS API Families" in permission_text
    assert "`infra/terraform/ecs.tf`" in permission_text
    assert "`infra/terraform/alb.tf`" in permission_text
    assert "Creation of service was not idempotent" in permission_text


def test_infra_inventory_check_script_passes_in_repo_state() -> None:
    repo_root = _repo_root()
    result = subprocess.run(
        [sys.executable, "infra/scripts/check_infra_inventory.py", "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
