"""Add captions and resilient temporary deletion metadata.

Revision ID: 0003_captions_editing_and_temporary_deletions
Revises: 0002_file_storage_and_deep_links
Create Date: 2026-06-10 01:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine[object]:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()
    op.add_column("files", sa.Column("caption_entities", json_type, nullable=True))
    op.add_column("file_variants", sa.Column("media_type", sa.String(length=50), nullable=False, server_default="document"))
    op.add_column("file_variants", sa.Column("caption", sa.Text(), nullable=True))
    op.add_column("file_variants", sa.Column("caption_entities", json_type, nullable=True))
    op.create_index("ix_file_variants_media_type", "file_variants", ["media_type"])

    op.add_column("temporary_messages", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_temporary_messages_user_id_users",
        "temporary_messages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_temporary_messages_user_id", "temporary_messages", ["user_id"])
    op.alter_column(
        "temporary_messages",
        "delete_after",
        new_column_name="delete_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.drop_index("ix_temporary_messages_delete_after", table_name="temporary_messages")
    op.create_index("ix_temporary_messages_delete_at", "temporary_messages", ["delete_at"])


def downgrade() -> None:
    op.drop_index("ix_temporary_messages_delete_at", table_name="temporary_messages")
    op.alter_column(
        "temporary_messages",
        "delete_at",
        new_column_name="delete_after",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.create_index("ix_temporary_messages_delete_after", "temporary_messages", ["delete_after"])
    op.drop_index("ix_temporary_messages_user_id", table_name="temporary_messages")
    op.drop_constraint("fk_temporary_messages_user_id_users", "temporary_messages", type_="foreignkey")
    op.drop_column("temporary_messages", "user_id")

    op.drop_index("ix_file_variants_media_type", table_name="file_variants")
    op.drop_column("file_variants", "caption_entities")
    op.drop_column("file_variants", "caption")
    op.drop_column("file_variants", "media_type")
    op.drop_column("files", "caption_entities")
