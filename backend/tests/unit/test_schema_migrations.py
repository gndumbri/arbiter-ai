"""Guards against ORM/migration drift for critical auth columns."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_users_default_ruling_privacy_has_migration() -> None:
    repo_root = _repo_root()
    versions_dir = repo_root / "backend" / "alembic" / "versions"
    assert versions_dir.exists(), f"Missing alembic versions directory: {versions_dir}"

    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(versions_dir.glob("*.py"))
    )

    assert "default_ruling_privacy" in migration_text
    assert "add_column(" in migration_text
    assert "\"users\"" in migration_text
