"""merge pgvector/provenance heads

Revision ID: f6a7b8c9d0e1
Revises: 3e3eccf9015e, d1e2f3a4b5c6
Create Date: 2026-02-15 10:40:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, tuple[str, str], None] = ("3e3eccf9015e", "d1e2f3a4b5c6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
