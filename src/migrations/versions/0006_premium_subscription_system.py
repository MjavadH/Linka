"""Premium subscription system.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-11 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "premium_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_premium_plans_name", "premium_plans", ["name"], unique=True)
    op.create_index("ix_premium_plans_is_active", "premium_plans", ["is_active"])

    op.add_column("subscriptions", sa.Column("plan_id", sa.Integer(), nullable=True))
    op.add_column("subscriptions", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_is_active", "subscriptions", ["is_active"])
    op.create_foreign_key("fk_subscriptions_plan_id_premium_plans", "subscriptions", "premium_plans", ["plan_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_constraint("fk_subscriptions_plan_id_premium_plans", "subscriptions", type_="foreignkey")
    op.drop_index("ix_subscriptions_is_active", table_name="subscriptions")
    op.drop_index("ix_subscriptions_plan_id", table_name="subscriptions")
    op.drop_column("subscriptions", "is_active")
    op.drop_column("subscriptions", "plan_id")
    op.drop_index("ix_premium_plans_is_active", table_name="premium_plans")
    op.drop_index("ix_premium_plans_name", table_name="premium_plans")
    op.drop_table("premium_plans")
