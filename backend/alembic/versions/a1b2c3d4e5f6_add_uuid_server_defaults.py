"""add gen_random_uuid() server defaults to UUID primary keys

WHY: The SQLAlchemy models used Python-side `default=uuid.uuid4`, which only
generates UUIDs when inserting via SQLAlchemy.  The frontend's DrizzleAdapter
inserts rows with `DEFAULT` for the id column, expecting the *database* to
generate the UUID.  Without a server_default, PostgreSQL inserts NULL and
violates the NOT NULL constraint.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-02-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table whose primary key is a UUID column named "id".
_TABLES = [
    "users",
    "accounts",
    "auth_sessions",
    "sessions",
    "ruleset_metadata",
    "publishers",
    "official_rulesets",
    "rule_chunks",
    "subscriptions",
    "subscription_tiers",
    "parties",
    "user_game_library",
    "saved_rulings",
    "query_audit_log",
]


def upgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "id",
            server_default=op.inline_literal("gen_random_uuid()"),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "id", server_default=None)
