"""add_role_to_users

Revision ID: b9f2a3c4d5e6
Revises: 4fc7b20cadfa
Create Date: 2026-02-14 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b9f2a3c4d5e6'
down_revision: str | None = '4fc7b20cadfa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(), server_default='USER', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'role')
