"""Add per-user Twilio connections and AI voice settings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260728_0006"
down_revision = "20260728_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "twilio_connections" not in tables:
        op.create_table(
            "twilio_connections",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("account_sid", sa.String(80), nullable=False, server_default=""),
            sa.Column("auth_token_encrypted", sa.Text(), nullable=False, server_default=""),
            sa.Column("phone_number", sa.String(40), nullable=False, server_default=""),
            sa.Column("phone_sid", sa.String(80), nullable=False, server_default=""),
            sa.Column("friendly_name", sa.String(160), nullable=False, server_default=""),
            sa.Column("account_status", sa.String(40), nullable=False, server_default=""),
            sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.String(500), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_twilio_connections_user_id", "twilio_connections", ["user_id"])
        op.create_index("ix_twilio_connections_account_sid", "twilio_connections", ["account_sid"])
        op.create_index("ix_twilio_connections_phone_number", "twilio_connections", ["phone_number"])
        op.create_index("ix_twilio_connections_is_connected", "twilio_connections", ["is_connected"])
        op.create_index("ix_twilio_connections_is_active", "twilio_connections", ["is_active"])

    if "voice_settings" not in tables:
        op.create_table(
            "voice_settings",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("voice_provider", sa.String(40), nullable=False, server_default="cartesia"),
            sa.Column("voice_id", sa.String(160), nullable=False, server_default=""),
            sa.Column("voice_name", sa.String(160), nullable=False, server_default=""),
            sa.Column("speaking_speed", sa.String(20), nullable=False, server_default="normal"),
            sa.Column("language", sa.String(20), nullable=False, server_default="en"),
            sa.Column("ai_greeting", sa.Text(), nullable=False, server_default=""),
            sa.Column("business_name", sa.String(160), nullable=False, server_default=""),
            sa.Column("assistant_name", sa.String(120), nullable=False, server_default=""),
            sa.Column("cartesia_api_key_encrypted", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", name="uq_voice_settings_user_id"),
        )
        op.create_index("ix_voice_settings_user_id", "voice_settings", ["user_id"])


def downgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "voice_settings" in tables:
        op.drop_index("ix_voice_settings_user_id", table_name="voice_settings")
        op.drop_table("voice_settings")
    if "twilio_connections" in tables:
        op.drop_index("ix_twilio_connections_is_active", table_name="twilio_connections")
        op.drop_index("ix_twilio_connections_is_connected", table_name="twilio_connections")
        op.drop_index("ix_twilio_connections_phone_number", table_name="twilio_connections")
        op.drop_index("ix_twilio_connections_account_sid", table_name="twilio_connections")
        op.drop_index("ix_twilio_connections_user_id", table_name="twilio_connections")
        op.drop_table("twilio_connections")
