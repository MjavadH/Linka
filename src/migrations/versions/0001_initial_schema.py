"""Initial normalized Linka schema.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-06-09 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    access_level = sa.Enum("FREE", "PREMIUM", name="fileaccesslevel")
    subscription_source = sa.Enum("MANUAL", "PAYMENT_REQUEST", name="subscriptionsource")
    payment_status = sa.Enum("PENDING", "APPROVED", "REJECTED", name="paymentrequeststatus")
    temp_status = sa.Enum("PENDING", "DELETED", "FAILED", name="temporarymessagestatus")
    broadcast_status = sa.Enum("DRAFT", "RUNNING", "PAUSED", "COMPLETED", "FAILED", name="broadcaststatus")
    recipient_status = sa.Enum("PENDING", "SENT", "FAILED", name="broadcastrecipientstatus")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total_downloads", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table("files", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(500), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("file_variants", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("quality", sa.String(50), nullable=False), sa.Column("telegram_file_id", sa.Text(), nullable=False), sa.Column("telegram_file_unique_id", sa.Text()), sa.Column("mime_type", sa.String(255)), sa.Column("file_size", sa.Integer()), sa.Column("access_level", access_level, nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.UniqueConstraint("file_id", "quality", name="uq_file_variants_file_quality"))
    op.create_index("ix_file_variants_file_id", "file_variants", ["file_id"])
    op.create_table("deep_links", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("token", sa.String(255), nullable=False), sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("variant_id", sa.Integer(), sa.ForeignKey("file_variants.id")), sa.Column("requires_premium", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_deep_links_token", "deep_links", ["token"], unique=True)
    op.create_index("ix_deep_links_file_id", "deep_links", ["file_id"])

    op.create_table("sponsors", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("chat_id", sa.BigInteger(), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("invite_url", sa.String(1024), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.Column("current_member_count", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_sponsors_chat_id", "sponsors", ["chat_id"], unique=True)
    op.create_table("sponsor_campaigns", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("starts_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("target_member_count", sa.Integer()), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
    op.create_table("sponsor_requirements", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("sponsor_campaigns.id", ondelete="CASCADE"), nullable=False), sa.Column("sponsor_id", sa.Integer(), sa.ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.UniqueConstraint("campaign_id", "sponsor_id", name="uq_campaign_sponsor"))

    op.create_table("subscriptions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("source", subscription_source, nullable=False), sa.Column("note", sa.Text()), sa.Column("granted_by_admin_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"])
    op.create_table("payment_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("phone_number", sa.String(50), nullable=False), sa.Column("payment_notes", sa.Text()), sa.Column("screenshots_metadata", postgresql.JSONB(), nullable=False, server_default="[]"), sa.Column("status", payment_status, nullable=False), sa.Column("reviewed_by_admin_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("review_note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_payment_requests_user_id", "payment_requests", ["user_id"])
    op.create_index("ix_payment_requests_status", "payment_requests", ["status"])

    op.create_table("downloads", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False), sa.Column("variant_id", sa.Integer(), sa.ForeignKey("file_variants.id")), sa.Column("deep_link_id", sa.Integer(), sa.ForeignKey("deep_links.id")), sa.Column("token", sa.String(255)), sa.Column("is_premium_download", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_downloads_user_id", "downloads", ["user_id"])
    op.create_index("ix_downloads_file_id", "downloads", ["file_id"])
    op.create_index("ix_downloads_created_at", "downloads", ["created_at"])

    op.create_table("temporary_messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("chat_id", sa.BigInteger(), nullable=False), sa.Column("message_id", sa.Integer(), nullable=False), sa.Column("delete_after", sa.DateTime(timezone=True), nullable=False), sa.Column("status", temp_status, nullable=False), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_error", sa.String(1000)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_temporary_messages_chat_id", "temporary_messages", ["chat_id"])
    op.create_index("ix_temporary_messages_delete_after", "temporary_messages", ["delete_after"])
    op.create_index("ix_temporary_messages_status", "temporary_messages", ["status"])

    op.create_table("broadcasts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("kind", sa.String(50), nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("status", broadcast_status, nullable=False), sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"), sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("cursor_user_id", sa.Integer()), sa.Column("failure_log", postgresql.JSONB(), nullable=False, server_default="[]"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("broadcast_recipients", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("broadcast_id", sa.Integer(), sa.ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False), sa.Column("telegram_id", sa.BigInteger(), nullable=False), sa.Column("status", recipient_status, nullable=False), sa.Column("message_id", sa.Integer()), sa.Column("error", sa.Text()), sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_index("ix_broadcast_recipients_broadcast_id", "broadcast_recipients", ["broadcast_id"])
    op.create_index("ix_broadcast_recipients_telegram_id", "broadcast_recipients", ["telegram_id"])
    op.create_index("ix_broadcast_recipients_status", "broadcast_recipients", ["status"])


def downgrade() -> None:
    op.drop_table("broadcast_recipients")
    op.drop_table("broadcasts")
    op.drop_table("temporary_messages")
    op.drop_table("downloads")
    op.drop_table("payment_requests")
    op.drop_table("subscriptions")
    op.drop_table("sponsor_requirements")
    op.drop_table("sponsor_campaigns")
    op.drop_table("sponsors")
    op.drop_table("deep_links")
    op.drop_table("file_variants")
    op.drop_table("files")
    op.drop_table("users")
    for enum_name in ["broadcastrecipientstatus", "broadcaststatus", "temporarymessagestatus", "paymentrequeststatus", "subscriptionsource", "fileaccesslevel"]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
