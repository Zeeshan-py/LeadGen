"""Add Paddle Billing subscription tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260731_0007"
down_revision = "20260728_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "paddle_customers" not in tables:
        op.create_table(
            "paddle_customers",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("customer_id", sa.String(80), nullable=False),
            sa.Column("email", sa.String(320), nullable=False, server_default=""),
            sa.Column("name", sa.String(160), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default=""),
            sa.Column("raw", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("customer_id", name="uq_paddle_customers_customer_id"),
            sa.UniqueConstraint("user_id", name="uq_paddle_customers_user_id"),
        )
        op.create_index("ix_paddle_customers_user_id", "paddle_customers", ["user_id"])
        op.create_index("ix_paddle_customers_customer_id", "paddle_customers", ["customer_id"])
        op.create_index("ix_paddle_customers_email", "paddle_customers", ["email"])

    if "paddle_subscriptions" not in tables:
        op.create_table(
            "paddle_subscriptions",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("subscription_id", sa.String(80), nullable=False),
            sa.Column("customer_id", sa.String(80), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default=""),
            sa.Column("plan_key", sa.String(60), nullable=False, server_default=""),
            sa.Column("price_id", sa.String(80), nullable=False, server_default=""),
            sa.Column("product_id", sa.String(80), nullable=False, server_default=""),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("currency_code", sa.String(10), nullable=False, server_default=""),
            sa.Column("billing_interval", sa.String(20), nullable=False, server_default=""),
            sa.Column("billing_frequency", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_billed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_billed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scheduled_change_action", sa.String(40), nullable=False, server_default=""),
            sa.Column("scheduled_change_effective_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("management_urls", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("custom_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("raw", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("subscription_id", name="uq_paddle_subscriptions_subscription_id"),
        )
        op.create_index("ix_paddle_subscriptions_user_id", "paddle_subscriptions", ["user_id"])
        op.create_index("ix_paddle_subscriptions_subscription_id", "paddle_subscriptions", ["subscription_id"])
        op.create_index("ix_paddle_subscriptions_customer_id", "paddle_subscriptions", ["customer_id"])
        op.create_index("ix_paddle_subscriptions_status", "paddle_subscriptions", ["status"])
        op.create_index("ix_paddle_subscriptions_plan_key", "paddle_subscriptions", ["plan_key"])
        op.create_index("ix_paddle_subscriptions_price_id", "paddle_subscriptions", ["price_id"])
        op.create_index("ix_paddle_subscriptions_product_id", "paddle_subscriptions", ["product_id"])

    if "paddle_transactions" not in tables:
        op.create_table(
            "paddle_transactions",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("transaction_id", sa.String(80), nullable=False),
            sa.Column("customer_id", sa.String(80), nullable=False, server_default=""),
            sa.Column("subscription_id", sa.String(80), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default=""),
            sa.Column("invoice_number", sa.String(80), nullable=False, server_default=""),
            sa.Column("currency_code", sa.String(10), nullable=False, server_default=""),
            sa.Column("subtotal", sa.String(40), nullable=False, server_default=""),
            sa.Column("tax", sa.String(40), nullable=False, server_default=""),
            sa.Column("total", sa.String(40), nullable=False, server_default=""),
            sa.Column("billed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("invoice_url", sa.String(1000), nullable=False, server_default=""),
            sa.Column("raw", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("transaction_id", name="uq_paddle_transactions_transaction_id"),
        )
        op.create_index("ix_paddle_transactions_user_id", "paddle_transactions", ["user_id"])
        op.create_index("ix_paddle_transactions_transaction_id", "paddle_transactions", ["transaction_id"])
        op.create_index("ix_paddle_transactions_customer_id", "paddle_transactions", ["customer_id"])
        op.create_index("ix_paddle_transactions_subscription_id", "paddle_transactions", ["subscription_id"])
        op.create_index("ix_paddle_transactions_status", "paddle_transactions", ["status"])
        op.create_index("ix_paddle_transactions_invoice_number", "paddle_transactions", ["invoice_number"])
        op.create_index("ix_paddle_transactions_billed_at", "paddle_transactions", ["billed_at"])

    if "paddle_webhook_events" not in tables:
        op.create_table(
            "paddle_webhook_events",
            sa.Column("id", sa.String(120), primary_key=True),
            sa.Column("event_type", sa.String(120), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_paddle_webhook_events_event_type", "paddle_webhook_events", ["event_type"])


def downgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "paddle_webhook_events" in tables:
        op.drop_index("ix_paddle_webhook_events_event_type", table_name="paddle_webhook_events")
        op.drop_table("paddle_webhook_events")
    if "paddle_transactions" in tables:
        op.drop_index("ix_paddle_transactions_billed_at", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_invoice_number", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_status", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_subscription_id", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_customer_id", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_transaction_id", table_name="paddle_transactions")
        op.drop_index("ix_paddle_transactions_user_id", table_name="paddle_transactions")
        op.drop_table("paddle_transactions")
    if "paddle_subscriptions" in tables:
        op.drop_index("ix_paddle_subscriptions_product_id", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_price_id", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_plan_key", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_status", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_customer_id", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_subscription_id", table_name="paddle_subscriptions")
        op.drop_index("ix_paddle_subscriptions_user_id", table_name="paddle_subscriptions")
        op.drop_table("paddle_subscriptions")
    if "paddle_customers" in tables:
        op.drop_index("ix_paddle_customers_email", table_name="paddle_customers")
        op.drop_index("ix_paddle_customers_customer_id", table_name="paddle_customers")
        op.drop_index("ix_paddle_customers_user_id", table_name="paddle_customers")
        op.drop_table("paddle_customers")
