"""add default_ruling_privacy to users

Revision ID: 6c5b4a3d2e1f
Revises: 0a1b2c3d4e5f
Create Date: 2026-02-15 19:05:00.000000

WHY: The SQLAlchemy User model includes users.default_ruling_privacy, but no
previous migration added the column. In production this causes authenticated
routes to fail with 500 when loading User rows.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c5b4a3d2e1f"
down_revision: str | Sequence[str] | None = "0a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "default_ruling_privacy",
            sa.String(),
            nullable=False,
            server_default="PRIVATE",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "default_ruling_privacy")
