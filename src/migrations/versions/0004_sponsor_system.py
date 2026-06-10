"""Add sponsor verification state and sponsor lifecycle fields.

Revision ID: 0004_sponsor_system
Revises: 0003_captions_editing_and_temporary_deletions
Create Date: 2026-06-10 02:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sponsor_status = sa.Enum("PENDING", "VERIFIED", "REVOKED", name="sponsorstatus")
    sponsor_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column("sponsor_status", sponsor_status, nullable=False, server_default="PENDING"),
    )
    op.add_column("users", sa.Column("sponsor_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_sponsor_check_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_sponsor_status", "users", ["sponsor_status"])
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])

    op.add_column("sponsors", sa.Column("channel_username", sa.String(length=255), nullable=True))
    op.add_column(
        "sponsors",
        sa.Column("expiration_type", sa.String(length=20), nullable=False, server_default="none"),
    )
    op.add_column("sponsors", sa.Column("expiration_value", sa.String(length=255), nullable=True))
    op.add_column(
        "sponsors",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sponsors_is_active", "sponsors", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_sponsors_is_active", table_name="sponsors")
    op.drop_column("sponsors", "updated_at")
    op.drop_column("sponsors", "expiration_value")
    op.drop_column("sponsors", "expiration_type")
    op.drop_column("sponsors", "channel_username")

    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_index("ix_users_sponsor_status", table_name="users")
    op.drop_column("users", "last_sponsor_check_at")
    op.drop_column("users", "sponsor_verified_at")
    op.drop_column("users", "sponsor_status")
    sa.Enum(name="sponsorstatus").drop(op.get_bind(), checkfirst=True)
