"""002 — Expand memory_entries + add memory_keyword_index table.

Revision ID: 002_memory_expansion
Revises: 001_initial
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "002_memory_expansion"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add columns to memory_entries ──
    op.add_column("memory_entries", sa.Column("memory_type", sa.String(30), nullable=False, server_default="general"))
    op.add_column("memory_entries", sa.Column("embedding_id", sa.String(200), nullable=True))
    op.add_column("memory_entries", sa.Column("keywords", sa.JSON(), nullable=True))
    op.add_column("memory_entries", sa.Column("importance_score", sa.Float(), server_default="0.5"))
    op.add_column("memory_entries", sa.Column("access_count", sa.Integer(), server_default="0"))
    op.add_column("memory_entries", sa.Column("last_accessed", sa.DateTime(), nullable=True))
    op.add_column("memory_entries", sa.Column("expires_at", sa.DateTime(), nullable=True))

    # ── Create memory_keyword_index ──
    op.create_table(
        "memory_keyword_index",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("memory_id", sa.String(), sa.ForeignKey("memory_entries.id"), nullable=False),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("tf_score", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_keyword_index_memory_id", "memory_keyword_index", ["memory_id"])
    op.create_index("ix_memory_keyword_index_keyword", "memory_keyword_index", ["keyword"])
    op.create_index("ix_memory_keyword_lookup", "memory_keyword_index", ["keyword", "memory_id"])


def downgrade() -> None:
    op.drop_table("memory_keyword_index")
    op.drop_column("memory_entries", "expires_at")
    op.drop_column("memory_entries", "last_accessed")
    op.drop_column("memory_entries", "access_count")
    op.drop_column("memory_entries", "importance_score")
    op.drop_column("memory_entries", "keywords")
    op.drop_column("memory_entries", "embedding_id")
    op.drop_column("memory_entries", "memory_type")
