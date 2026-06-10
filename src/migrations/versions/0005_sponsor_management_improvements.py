"""Add sponsor management metadata.

Revision ID: 0005_sponsor_management_improvements
Revises: 0004_sponsor_system
Create Date: 2026-06-10 03:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sponsors", sa.Column("chat_type", sa.String(length=50), nullable=True))
    op.add_column(
        "sponsors",
        sa.Column("sponsor_join_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sponsors", "sponsor_join_count")
    op.drop_column("sponsors", "chat_type")
