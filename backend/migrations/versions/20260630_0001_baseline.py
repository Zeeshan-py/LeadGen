"""Create the production database baseline and upgrade legacy installations."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260630_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())

    if "campaigns" not in existing:
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("city", sa.String(120), nullable=False, server_default=""),
            sa.Column("state", sa.String(120), nullable=False, server_default=""),
            sa.Column("country", sa.String(120), nullable=False, server_default=""),
            sa.Column("continent", sa.String(80), nullable=False, server_default=""),
            sa.Column("business_type", sa.String(160), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("max_leads", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("leads_generated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("replies", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "leads" not in existing:
        op.create_table(
            "leads",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("campaign_id", sa.Uuid(as_uuid=False), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
            sa.Column("dedupe_key", sa.String(255), nullable=False),
            sa.Column("business_name", sa.String(240), nullable=False),
            sa.Column("website", sa.String(500), nullable=False, server_default=""),
            sa.Column("google_maps_url", sa.String(800), nullable=False, server_default=""),
            sa.Column("email", sa.String(320), nullable=False, server_default=""),
            sa.Column("phone", sa.String(80), nullable=False, server_default=""),
            sa.Column("location", sa.String(500), nullable=False, server_default=""),
            sa.Column("city", sa.String(120), nullable=False, server_default=""),
            sa.Column("state", sa.String(120), nullable=False, server_default=""),
            sa.Column("country", sa.String(120), nullable=False, server_default=""),
            sa.Column("business_type", sa.String(160), nullable=False, server_default=""),
            sa.Column("website_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("opportunity_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("website_problems", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("website_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("improvement_suggestions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("lead_status", sa.String(40), nullable=False, server_default="qualified"),
            sa.Column("outreach_status", sa.String(40), nullable=False, server_default="not_started"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("social_links", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("social_status", sa.String(40), nullable=False, server_default="missing"),
            sa.Column("screenshot_url", sa.String(800), nullable=False, server_default=""),
            sa.Column("source", sa.String(80), nullable=False, server_default="apify_google_maps"),
            sa.Column("raw", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("dedupe_key", name="uq_leads_dedupe_key"),
        )

    if "outreach" not in existing:
        op.create_table(
            "outreach",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("lead_id", sa.Uuid(as_uuid=False), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campaign_id", sa.Uuid(as_uuid=False), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
            sa.Column("subject_line", sa.String(220), nullable=False, server_default=""),
            sa.Column("personalized_first_line", sa.Text(), nullable=False, server_default=""),
            sa.Column("cold_email", sa.Text(), nullable=False, server_default=""),
            sa.Column("follow_up_1", sa.Text(), nullable=False, server_default=""),
            sa.Column("follow_up_2", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_version", sa.String(40), nullable=False, server_default="cold_email"),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("gmail_message_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("gmail_thread_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("tracking_id", sa.String(64), nullable=False, server_default=""),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
            sa.Column("opened_at", sa.DateTime(timezone=True)),
            sa.Column("replied_at", sa.DateTime(timezone=True)),
            sa.Column("bounced_at", sa.DateTime(timezone=True)),
            sa.Column("failed_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "analytics" not in existing:
        op.create_table(
            "analytics",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("lead_id", sa.Uuid(as_uuid=False), sa.ForeignKey("leads.id", ondelete="SET NULL")),
            sa.Column("campaign_id", sa.Uuid(as_uuid=False), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "settings" not in existing:
        op.create_table(
            "settings",
            sa.Column("key", sa.String(120), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "lead_generation_jobs" not in existing:
        op.create_table(
            "lead_generation_jobs",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("campaign_id", sa.Uuid(as_uuid=False), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
            sa.Column("city", sa.String(120), nullable=False, server_default=""),
            sa.Column("state", sa.String(120), nullable=False, server_default=""),
            sa.Column("country", sa.String(120), nullable=False, server_default=""),
            sa.Column("continent", sa.String(80), nullable=False, server_default=""),
            sa.Column("business_type", sa.String(160), nullable=False, server_default=""),
            sa.Column("website_mode", sa.String(40), nullable=False, server_default="withWebsite"),
            sa.Column("max_leads", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lead_counter", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_counter", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_counter", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
        )

    _upgrade_legacy_columns()
    _create_indexes()


def _upgrade_legacy_columns() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("leads")}
    if "social_links" not in columns:
        op.add_column("leads", sa.Column("social_links", sa.JSON(), nullable=False, server_default="{}"))
    if "social_status" not in columns:
        op.add_column("leads", sa.Column("social_status", sa.String(40), nullable=False, server_default="missing"))

    for table_name in ("campaigns", "lead_generation_jobs"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "continent" not in columns:
            op.add_column(table_name, sa.Column("continent", sa.String(80), nullable=False, server_default=""))


def _create_indexes() -> None:
    desired = {
        "campaigns": {"ix_campaigns_name": ["name"], "ix_campaigns_status": ["status"]},
        "leads": {
            "ix_leads_campaign_id": ["campaign_id"],
            "ix_leads_dedupe_key": ["dedupe_key"],
            "ix_leads_email": ["email"],
            "ix_leads_business_type": ["business_type"],
            "ix_leads_lead_status": ["lead_status"],
            "ix_leads_outreach_status": ["outreach_status"],
            "ix_leads_social_status": ["social_status"],
        },
        "outreach": {
            "ix_outreach_lead_id": ["lead_id"],
            "ix_outreach_campaign_id": ["campaign_id"],
            "ix_outreach_status": ["status"],
            "ix_outreach_tracking_id": ["tracking_id"],
        },
        "analytics": {
            "ix_analytics_event_type": ["event_type"],
            "ix_analytics_lead_id": ["lead_id"],
            "ix_analytics_campaign_id": ["campaign_id"],
            "ix_analytics_created_at": ["created_at"],
        },
        "lead_generation_jobs": {
            "ix_lead_generation_jobs_campaign_id": ["campaign_id"],
            "ix_lead_generation_jobs_status": ["status"],
        },
    }
    inspector = inspect(op.get_bind())
    for table_name, indexes in desired.items():
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        for name, columns in indexes.items():
            if name not in existing:
                op.create_index(name, table_name, columns)


def downgrade() -> None:
    # This baseline intentionally preserves production data.
    pass
