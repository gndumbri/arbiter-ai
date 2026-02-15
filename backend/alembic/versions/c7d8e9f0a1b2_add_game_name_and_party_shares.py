"""Add game_name to rulings, status to party_members, party_game_shares table.

Revision ID: c7d8e9f0a1b2
Revises: 053437c609a1
Create Date: 2026-02-14

WHY: SavedRuling needs game_name for game-based filtering/grouping.
PartyMember needs status for invite acceptance flow.
PartyGameShare enables per-game visibility control in parties.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "053437c609a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- SavedRuling: add game context ---
    op.add_column("saved_rulings", sa.Column("game_name", sa.String(), nullable=True))
    op.add_column(
        "saved_rulings",
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_saved_rulings_game_name", "saved_rulings", ["game_name"])
    op.create_foreign_key(
        "fk_saved_rulings_session_id",
        "saved_rulings",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- PartyMember: invite acceptance flow ---
    op.add_column(
        "party_members",
        sa.Column("status", sa.String(), nullable=False, server_default="ACCEPTED"),
    )

    # --- PartyGameShare: per-game visibility ---
    op.create_table(
        "party_game_shares",
        sa.Column("party_id", UUID(as_uuid=True), sa.ForeignKey("parties.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("game_name", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("party_game_shares")
    op.drop_column("party_members", "status")
    op.drop_constraint("fk_saved_rulings_session_id", "saved_rulings", type_="foreignkey")
    op.drop_index("ix_saved_rulings_game_name", table_name="saved_rulings")
    op.drop_column("saved_rulings", "session_id")
    op.drop_column("saved_rulings", "game_name")
