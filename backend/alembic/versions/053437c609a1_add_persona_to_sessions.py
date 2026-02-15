"""add persona to sessions

Revision ID: 053437c609a1
Revises: 12bf466e36fd
Create Date: 2026-02-14 15:15:11.456316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '053437c609a1'
down_revision: Union[str, None] = '12bf466e36fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WHY: Use IF NOT EXISTS to make this migration safe on partially
    # migrated local databases where columns may already exist.
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS persona VARCHAR")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS system_prompt_override TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS system_prompt_override")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS persona")
