"""Production hardening audit logs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-13 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("admin_username", sa.String(length=255), nullable=True),
        sa.Column("admin_full_name", sa.String(length=500), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_admin_user_id", "audit_logs", ["admin_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_type", "audit_logs", ["target_type"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_created_id", "audit_logs", ["created_at", "id"])
    op.create_index("ix_audit_logs_action_created", "audit_logs", ["action", "created_at"])
    op.create_index("ix_audit_logs_admin_created", "audit_logs", ["admin_user_id", "created_at"])


def downgrade() -> None:
    for name in [
        "ix_audit_logs_admin_created", "ix_audit_logs_action_created", "ix_audit_logs_created_id",
        "ix_audit_logs_target_id", "ix_audit_logs_target_type", "ix_audit_logs_action",
        "ix_audit_logs_admin_user_id", "ix_audit_logs_created_at",
    ]:
        op.drop_index(name, table_name="audit_logs")
    op.drop_table("audit_logs")
