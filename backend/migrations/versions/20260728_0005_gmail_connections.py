"""Add per-user Gmail OAuth connections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260728_0005"
down_revision = "20260726_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "gmail_connections" in set(inspector.get_table_names()):
        return

    op.create_table(
        "gmail_connections",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gmail_email", sa.String(320), nullable=False, server_default=""),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_gmail_connections_user_id"),
    )
    op.create_index("ix_gmail_connections_user_id", "gmail_connections", ["user_id"])
    op.create_index("ix_gmail_connections_gmail_email", "gmail_connections", ["gmail_email"])
    op.create_index("ix_gmail_connections_is_connected", "gmail_connections", ["is_connected"])


def downgrade() -> None:
    if "gmail_connections" in set(inspect(op.get_bind()).get_table_names()):
        op.drop_index("ix_gmail_connections_is_connected", table_name="gmail_connections")
        op.drop_index("ix_gmail_connections_gmail_email", table_name="gmail_connections")
        op.drop_index("ix_gmail_connections_user_id", table_name="gmail_connections")
        op.drop_table("gmail_connections")
