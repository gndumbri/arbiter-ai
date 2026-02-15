"""Ensure session persona columns exist.

Revision ID: 8f1e2d3c4b5a
Revises: f6a7b8c9d0e1
Create Date: 2026-02-15 15:24:00.000000

WHY: Some local databases were out of sync with historical branch merges and
did not have sessions.persona/system_prompt_override despite later code
expecting those fields.
"""

from alembic import op

revision = "8f1e2d3c4b5a"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS persona VARCHAR")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS system_prompt_override TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS system_prompt_override")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS persona")
