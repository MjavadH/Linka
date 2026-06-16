"""Premium reminder tracking.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-16 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("reminder_7d_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("reminder_3d_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("reminder_1d_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("expiration_notified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "expiration_notified_at")
    op.drop_column("subscriptions", "reminder_1d_sent_at")
    op.drop_column("subscriptions", "reminder_3d_sent_at")
    op.drop_column("subscriptions", "reminder_7d_sent_at")
