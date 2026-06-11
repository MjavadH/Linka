"""User management bans.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-11 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_bans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_permanent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(length=255), nullable=False, server_default="admin_ban"),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_bans_user_id", "user_bans", ["user_id"])
    op.create_index("ix_user_bans_is_active", "user_bans", ["is_active"])
    op.create_index("ix_user_bans_is_permanent", "user_bans", ["is_permanent"])
    op.create_index("ix_user_bans_banned_until", "user_bans", ["banned_until"])


def downgrade() -> None:
    op.drop_index("ix_user_bans_banned_until", table_name="user_bans")
    op.drop_index("ix_user_bans_is_permanent", table_name="user_bans")
    op.drop_index("ix_user_bans_is_active", table_name="user_bans")
    op.drop_index("ix_user_bans_user_id", table_name="user_bans")
    op.drop_table("user_bans")
