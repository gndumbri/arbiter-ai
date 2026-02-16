"""Regression guards for backend container packaging."""

from __future__ import annotations

from pathlib import Path


def _read_backend_dockerfile() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    dockerfile = repo_root / "backend" / "Dockerfile"
    assert dockerfile.exists(), f"Missing Dockerfile: {dockerfile}"
    return dockerfile.read_text(encoding="utf-8")


def test_backend_image_includes_scripts_for_catalog_bootstrap() -> None:
    text = _read_backend_dockerfile()

    assert "COPY scripts/ ./scripts/" in text
