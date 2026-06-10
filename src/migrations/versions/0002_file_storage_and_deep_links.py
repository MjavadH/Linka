"""Add provider-agnostic file storage metadata.

Revision ID: 0002_file_storage_and_deep_links
Revises: 0001_initial_schema
Create Date: 2026-06-10 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_file_storage_and_deep_links"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    storage_type = sa.Enum("TELEGRAM", "MINIO", "S3", "LOCAL", name="storagetype")
    storage_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "file_variants",
        sa.Column("storage_type", storage_type, nullable=False, server_default="TELEGRAM"),
    )
    op.add_column("file_variants", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("file_variants", sa.Column("archive_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("file_variants", sa.Column("archive_message_id", sa.Integer(), nullable=True))
    op.add_column("file_variants", sa.Column("filename", sa.String(length=1024), nullable=True))
    op.add_column("file_variants", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("file_variants", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.alter_column("file_variants", "telegram_file_id", existing_type=sa.Text(), nullable=True)
    op.create_index("ix_file_variants_storage_type", "file_variants", ["storage_type"])

    op.execute(
        "UPDATE file_variants SET storage_key = 'telegram:file_id:' || telegram_file_id "
        "WHERE storage_key IS NULL"
    )
    op.alter_column("file_variants", "storage_key", nullable=False)

    op.alter_column(
        "deep_links",
        "variant_id",
        new_column_name="file_variant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.create_index("ix_deep_links_file_variant_id", "deep_links", ["file_variant_id"])


def downgrade() -> None:
    op.drop_index("ix_deep_links_file_variant_id", table_name="deep_links")
    op.alter_column(
        "deep_links",
        "file_variant_id",
        new_column_name="variant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column("file_variants", "telegram_file_id", existing_type=sa.Text(), nullable=False)
    op.drop_index("ix_file_variants_storage_type", table_name="file_variants")
    op.drop_column("file_variants", "created_at")
    op.drop_column("file_variants", "is_premium")
    op.drop_column("file_variants", "filename")
    op.drop_column("file_variants", "archive_message_id")
    op.drop_column("file_variants", "archive_chat_id")
    op.drop_column("file_variants", "storage_key")
    op.drop_column("file_variants", "storage_type")
    sa.Enum(name="storagetype").drop(op.get_bind(), checkfirst=True)
