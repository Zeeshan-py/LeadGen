"""Add authentication and private per-user workspace ownership."""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260726_0004"
down_revision = "20260707_0003"
branch_labels = None
depends_on = None

DEFAULT_ADMIN_USER_ID = "00000000-0000-0000-0000-000000000100"


def upgrade() -> None:
    bind = op.get_bind()
    admin_user_id = _ensure_users_table(bind)
    _ensure_auth_token_tables()
    _add_workspace_ownership(admin_user_id)
    _rebuild_uniqueness()
    _rebuild_settings_primary_key()


def _ensure_users_table(bind: sa.Connection) -> str:
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("full_name", sa.String(160), nullable=False, server_default=""),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False, server_default=""),
            sa.Column("provider", sa.String(40), nullable=False, server_default="email"),
            sa.Column("provider_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("avatar_url", sa.String(800), nullable=False, server_default=""),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_email", "users", ["email"])
        op.create_index("ix_users_provider", "users", ["provider"])
        op.create_index("ix_users_is_admin", "users", ["is_admin"])
        op.create_index("ix_users_is_verified", "users", ["is_verified"])

    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@leadforge.local").strip().lower()
    admin_user_id = bind.execute(
        sa.text("SELECT id FROM users WHERE lower(email) = :email LIMIT 1"),
        {"email": admin_email},
    ).scalar_one_or_none()
    if admin_user_id:
        bind.execute(
            sa.text("UPDATE users SET is_admin = true, is_verified = true WHERE id = :id"),
            {"id": admin_user_id},
        )
        return str(admin_user_id)

    bind.execute(
        sa.text(
            """
            INSERT INTO users (
                id, full_name, email, password_hash, provider, provider_id,
                avatar_url, is_admin, is_verified
            )
            VALUES (
                :id, 'LeadForge Admin', :email, '', 'email', '',
                '', true, true
            )
            """
        ),
        {"id": DEFAULT_ADMIN_USER_ID, "email": admin_email},
    )
    return DEFAULT_ADMIN_USER_ID


def _ensure_auth_token_tables() -> None:
    inspector = inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "refresh_tokens" not in existing:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("user_agent", sa.String(500), nullable=False, server_default=""),
            sa.Column("ip_address", sa.String(80), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
        op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    if "password_reset_tokens" not in existing:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])
        op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])


def _add_workspace_ownership(admin_user_id: str) -> None:
    tables = (
        "campaigns",
        "crm_users",
        "crm_tags",
        "leads",
        "lead_tags",
        "lead_notes",
        "lead_activities",
        "outreach",
        "email_messages",
        "analytics",
        "settings",
        "lead_generation_jobs",
        "ai_sdr_contact_batches",
        "ai_sdr_contact_records",
    )
    for table_name in tables:
        if _table_exists(table_name):
            _ensure_user_id_column(table_name, admin_user_id)

    bind = op.get_bind()
    if _table_exists("leads") and _table_exists("lead_tags"):
        bind.execute(
            sa.text(
                """
                UPDATE lead_tags
                SET user_id = leads.user_id
                FROM leads
                WHERE lead_tags.lead_id = leads.id
                """
            )
        )
    if _table_exists("ai_sdr_contact_batches") and _table_exists("ai_sdr_contact_records"):
        bind.execute(
            sa.text(
                """
                UPDATE ai_sdr_contact_records
                SET user_id = ai_sdr_contact_batches.user_id
                FROM ai_sdr_contact_batches
                WHERE ai_sdr_contact_records.batch_id = ai_sdr_contact_batches.id
                """
            )
        )


def _ensure_user_id_column(table_name: str, admin_user_id: str) -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "user_id" not in columns:
        op.add_column(
            table_name,
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=False),
                nullable=False,
                server_default=admin_user_id,
            ),
        )
    bind = op.get_bind()
    bind.execute(sa.text(f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL"), {"user_id": admin_user_id})
    with op.batch_alter_table(table_name) as batch:
        batch.alter_column("user_id", nullable=False, server_default=None)
    _create_index_if_missing(table_name, f"ix_{table_name}_user_id", ["user_id"])
    _create_fk_if_missing(table_name, f"fk_{table_name}_user_id_users", ["user_id"], "users", ["id"])


def _rebuild_uniqueness() -> None:
    replacements = (
        ("leads", "uq_leads_dedupe_key", "uq_leads_user_dedupe_key", ["user_id", "dedupe_key"]),
        ("crm_users", "uq_crm_users_email", "uq_crm_users_user_email", ["user_id", "email"]),
        ("crm_tags", "uq_crm_tags_name", "uq_crm_tags_user_name", ["user_id", "name"]),
        (
            "email_messages",
            "uq_email_messages_gmail_message_id",
            "uq_email_messages_user_gmail_message_id",
            ["user_id", "gmail_message_id"],
        ),
    )
    for table_name, old_name, new_name, columns in replacements:
        if not _table_exists(table_name):
            continue
        _drop_unique_if_exists(table_name, old_name)
        _create_unique_if_missing(table_name, new_name, columns)


def _rebuild_settings_primary_key() -> None:
    if not _table_exists("settings"):
        return
    inspector = inspect(op.get_bind())
    pk = inspector.get_pk_constraint("settings")
    columns = set(pk.get("constrained_columns") or [])
    if columns == {"user_id", "key"}:
        return
    pk_name = pk.get("name")
    if pk_name:
        op.drop_constraint(pk_name, "settings", type_="primary")
    op.create_primary_key("pk_settings_user_key", "settings", ["user_id", "key"])


def _table_exists(table_name: str) -> bool:
    return table_name in set(inspect(op.get_bind()).get_table_names())


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    existing = {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _create_fk_if_missing(
    table_name: str,
    constraint_name: str,
    local_columns: list[str],
    remote_table: str,
    remote_columns: list[str],
) -> None:
    existing = {constraint["name"] for constraint in inspect(op.get_bind()).get_foreign_keys(table_name)}
    if constraint_name not in existing:
        op.create_foreign_key(
            constraint_name,
            table_name,
            remote_table,
            local_columns,
            remote_columns,
            ondelete="CASCADE",
        )


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    existing = {constraint["name"] for constraint in inspect(op.get_bind()).get_unique_constraints(table_name)}
    if constraint_name in existing:
        op.drop_constraint(constraint_name, table_name, type_="unique")


def _create_unique_if_missing(table_name: str, constraint_name: str, columns: list[str]) -> None:
    existing = {constraint["name"] for constraint in inspect(op.get_bind()).get_unique_constraints(table_name)}
    if constraint_name not in existing:
        op.create_unique_constraint(constraint_name, table_name, columns)


def downgrade() -> None:
    # SaaS ownership migrations intentionally preserve production data.
    pass
