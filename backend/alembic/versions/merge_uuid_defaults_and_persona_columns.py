"""merge uuid_defaults and persona_columns heads

Revision ID: 0a1b2c3d4e5f
Revises: 8f1e2d3c4b5a, a1b2c3d4e5f6
Create Date: 2026-02-15 16:00:00.000000

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, tuple[str, ...], None] = (
    "8f1e2d3c4b5a",
    "a1b2c3d4e5f6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
