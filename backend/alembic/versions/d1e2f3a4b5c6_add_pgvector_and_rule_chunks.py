"""Add pgvector extension and rule_chunks table.

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-02-14 18:50:00.000000

WHY: This migration enables Postgres-native vector storage (replaces Pinecone).
     Legal provenance columns were already added in 3e3eccf9015e.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "d1e2f3a4b5c6"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WHY: pgvector extension MUST be created before any Vector columns.
    # Requires superuser or CREATE EXTENSION privilege on the database.
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as exc:
        raise RuntimeError(
            "pgvector extension is not available on this Postgres instance. "
            "Install/enable pgvector (or use a pgvector-enabled image) before running migrations."
        ) from exc

    # ── rule_chunks table with pgvector embedding ─────────────────────────
    op.create_table(
        "rule_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ruleset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("official_rulesets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("section_header", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        # WHY: 1024 dimensions matches Bedrock Titan Embed v2 output.
        # Using raw SQL because Alembic doesn't natively understand Vector().
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # WHY: The embedding column needs to be VECTOR type, not TEXT.
    # We alter it after table creation because Alembic's create_table
    # doesn't support the vector type natively.
    op.execute("ALTER TABLE rule_chunks ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)")

    # Index for fast similarity search filtered by ruleset
    op.create_index("ix_rule_chunks_ruleset_id", "rule_chunks", ["ruleset_id"])


def downgrade() -> None:
    op.drop_table("rule_chunks")
    # NOTE: We don't drop the vector extension — it may be used by other tables.
