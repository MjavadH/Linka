"""Add series and episode file management support.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-11 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    content_type = sa.Enum("MOVIE", "EPISODE", name="contenttype")
    content_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "files",
        sa.Column("content_type", content_type, nullable=False, server_default="MOVIE"),
    )
    op.create_index("ix_files_content_type", "files", ["content_type"])

    op.create_table(
        "series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("series_id", "number", name="uq_episodes_series_number"),
        sa.UniqueConstraint("file_id", name="uq_episodes_file_id"),
    )
    op.create_index("ix_episodes_series_id", "episodes", ["series_id"])
    op.create_index("ix_episodes_file_id", "episodes", ["file_id"])

    op.add_column("file_variants", sa.Column("episode_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_file_variants_episode_id_episodes",
        "file_variants",
        "episodes",
        ["episode_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_file_variants_episode_id", "file_variants", ["episode_id"])


def downgrade() -> None:
    op.drop_index("ix_file_variants_episode_id", table_name="file_variants")
    op.drop_constraint("fk_file_variants_episode_id_episodes", "file_variants", type_="foreignkey")
    op.drop_column("file_variants", "episode_id")
    op.drop_index("ix_episodes_file_id", table_name="episodes")
    op.drop_index("ix_episodes_series_id", table_name="episodes")
    op.drop_table("episodes")
    op.drop_table("series")
    op.drop_index("ix_files_content_type", table_name="files")
    op.drop_column("files", "content_type")
    sa.Enum(name="contenttype").drop(op.get_bind(), checkfirst=True)
