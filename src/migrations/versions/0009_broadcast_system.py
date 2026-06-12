"""Broadcast system.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-12 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    broadcast_status = sa.Enum("DRAFT", "RUNNING", "COMPLETED", "CANCELLED", "FAILED", name="broadcaststatus")
    target_type = sa.Enum("ALL", "PREMIUM", "FREE", name="broadcasttargettype")
    result_status = sa.Enum("PENDING", "SENT", "BLOCKED", "DELIVERY_ERROR", "FAILED", name="broadcastresultstatus")
    broadcast_status.create(op.get_bind(), checkfirst=True)
    op.execute("ALTER TYPE broadcaststatus ADD VALUE IF NOT EXISTS 'CANCELLED'")
    target_type.create(op.get_bind(), checkfirst=True)
    result_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "broadcast_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", broadcast_status, nullable=False),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivery_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("other_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("progress_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_broadcast_jobs_status", "broadcast_jobs", ["status"])
    op.create_index("ix_broadcast_jobs_target_type", "broadcast_jobs", ["target_type"])
    op.create_index("ix_broadcast_jobs_admin_telegram_id", "broadcast_jobs", ["admin_telegram_id"])

    op.create_table(
        "broadcast_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("broadcast_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", result_status, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broadcast_results_job_id", "broadcast_results", ["job_id"])
    op.create_index("ix_broadcast_results_telegram_id", "broadcast_results", ["telegram_id"])
    op.create_index("ix_broadcast_results_status", "broadcast_results", ["status"])


def downgrade() -> None:
    op.drop_index("ix_broadcast_results_status", table_name="broadcast_results")
    op.drop_index("ix_broadcast_results_telegram_id", table_name="broadcast_results")
    op.drop_index("ix_broadcast_results_job_id", table_name="broadcast_results")
    op.drop_table("broadcast_results")
    op.drop_index("ix_broadcast_jobs_admin_telegram_id", table_name="broadcast_jobs")
    op.drop_index("ix_broadcast_jobs_target_type", table_name="broadcast_jobs")
    op.drop_index("ix_broadcast_jobs_status", table_name="broadcast_jobs")
    op.drop_table("broadcast_jobs")
    for enum_name in ["broadcastresultstatus", "broadcasttargettype"]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
