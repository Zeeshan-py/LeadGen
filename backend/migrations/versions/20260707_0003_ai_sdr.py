"""Add independent AI SDR import tracking tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260707_0003"
down_revision = "20260702_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())

    if "ai_sdr_contact_batches" not in existing:
        op.create_table(
            "ai_sdr_contact_batches",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("source_type", sa.String(80), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("normalized_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stored_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(160), nullable=False, server_default="LeadForge AI SDR"),
            sa.Column("configuration", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ai_sdr_contact_batches_source_type", "ai_sdr_contact_batches", ["source_type"])
        op.create_index("ix_ai_sdr_contact_batches_status", "ai_sdr_contact_batches", ["status"])
        op.create_index(
            "ix_ai_sdr_contact_batches_source_status",
            "ai_sdr_contact_batches",
            ["source_type", "status"],
        )

    if "ai_sdr_contact_records" not in existing:
        op.create_table(
            "ai_sdr_contact_records",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "batch_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("ai_sdr_contact_batches.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "crm_lead_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("leads.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source_type", sa.String(80), nullable=False),
            sa.Column("external_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default="received"),
            sa.Column("dedupe_key", sa.String(255), nullable=False, server_default=""),
            sa.Column("normalized", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("raw", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("errors", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ai_sdr_contact_records_batch_id", "ai_sdr_contact_records", ["batch_id"])
        op.create_index("ix_ai_sdr_contact_records_crm_lead_id", "ai_sdr_contact_records", ["crm_lead_id"])
        op.create_index("ix_ai_sdr_contact_records_source_type", "ai_sdr_contact_records", ["source_type"])
        op.create_index("ix_ai_sdr_contact_records_external_id", "ai_sdr_contact_records", ["external_id"])
        op.create_index("ix_ai_sdr_contact_records_status", "ai_sdr_contact_records", ["status"])
        op.create_index("ix_ai_sdr_contact_records_dedupe_key", "ai_sdr_contact_records", ["dedupe_key"])
        op.create_index(
            "ix_ai_sdr_contact_records_batch_status",
            "ai_sdr_contact_records",
            ["batch_id", "status"],
        )


def downgrade() -> None:
    # Production data is preserved by design.
    pass
