"""Add the relational CRM, activity timeline, and Gmail conversation store."""

from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260702_0002"
down_revision = "20260630_0001"
branch_labels = None
depends_on = None

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())

    if "crm_users" not in existing:
        op.create_table(
            "crm_users",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("email", sa.String(320), nullable=False, server_default=""),
            sa.Column("initials", sa.String(8), nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("email", name="uq_crm_users_email"),
        )
        op.create_index("ix_crm_users_name", "crm_users", ["name"])
        op.create_index("ix_crm_users_email", "crm_users", ["email"])
        op.create_index("ix_crm_users_is_active", "crm_users", ["is_active"])

    bind.execute(
        sa.text(
            """
            INSERT INTO crm_users (id, name, email, initials, is_active)
            SELECT :id, 'LeadForge Admin', 'admin@leadforge.local', 'LA', true
            WHERE NOT EXISTS (
                SELECT 1 FROM crm_users WHERE email = 'admin@leadforge.local'
            )
            """
        ),
        {"id": DEFAULT_USER_ID},
    )

    lead_columns = {column["name"] for column in inspector.get_columns("leads")}
    if "contact_name" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("contact_name", sa.String(180), nullable=False, server_default=""),
        )
        op.create_index("ix_leads_contact_name", "leads", ["contact_name"])
    if "crm_stage" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("crm_stage", sa.String(40), nullable=False, server_default="qualified"),
        )
        op.create_index("ix_leads_crm_stage", "leads", ["crm_stage"])
    if "assigned_user_id" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("assigned_user_id", sa.Uuid(as_uuid=False), nullable=True),
        )
        op.create_foreign_key(
            "fk_leads_assigned_user_id",
            "leads",
            "crm_users",
            ["assigned_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_leads_assigned_user_id", "leads", ["assigned_user_id"])
    if "last_contacted_at" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_leads_last_contacted_at", "leads", ["last_contacted_at"])
    if "next_follow_up_at" not in lead_columns:
        op.add_column(
            "leads",
            sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_leads_next_follow_up_at", "leads", ["next_follow_up_at"])

    bind.execute(
        sa.text(
            """
            UPDATE leads
            SET crm_stage = CASE
                WHEN lead_status IN ('won', 'lost', 'archived', 'interested', 'meeting_scheduled')
                    THEN lead_status
                WHEN outreach_status = 'replied' THEN 'replied'
                WHEN outreach_status = 'opened' THEN 'opened'
                WHEN outreach_status = 'sent' THEN 'email_sent'
                WHEN outreach_status IN ('draft', 'generated') THEN 'email_generated'
                WHEN lead_status = 'new' THEN 'new'
                ELSE 'qualified'
            END
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE leads
            SET last_contacted_at = sent.sent_at
            FROM (
                SELECT lead_id, MAX(sent_at) AS sent_at
                FROM outreach
                WHERE sent_at IS NOT NULL
                GROUP BY lead_id
            ) AS sent
            WHERE leads.id = sent.lead_id
            """
        )
    )

    if "crm_tags" not in existing:
        op.create_table(
            "crm_tags",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("color", sa.String(40), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("name", name="uq_crm_tags_name"),
        )
        op.create_index("ix_crm_tags_name", "crm_tags", ["name"])

    if "lead_tags" not in existing:
        op.create_table(
            "lead_tags",
            sa.Column(
                "lead_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "tag_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("crm_tags.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_lead_tags_tag_id", "lead_tags", ["tag_id"])

    if "lead_notes" not in existing:
        op.create_table(
            "lead_notes",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "lead_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "created_by",
                sa.String(160),
                nullable=False,
                server_default="LeadForge user",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"])

    if "lead_activities" not in existing:
        op.create_table(
            "lead_activities",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "lead_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "actor",
                sa.String(160),
                nullable=False,
                server_default="LeadForge AI",
            ),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_lead_activities_lead_id", "lead_activities", ["lead_id"])
        op.create_index("ix_lead_activities_event_type", "lead_activities", ["event_type"])
        op.create_index("ix_lead_activities_created_at", "lead_activities", ["created_at"])

    if "email_messages" not in existing:
        op.create_table(
            "email_messages",
            sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column(
                "lead_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "outreach_id",
                sa.Uuid(as_uuid=False),
                sa.ForeignKey("outreach.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("gmail_message_id", sa.String(255), nullable=False),
            sa.Column("gmail_thread_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("message_id_header", sa.String(500), nullable=False, server_default=""),
            sa.Column("direction", sa.String(20), nullable=False),
            sa.Column("from_email", sa.String(320), nullable=False, server_default=""),
            sa.Column("to_email", sa.String(320), nullable=False, server_default=""),
            sa.Column("subject", sa.String(500), nullable=False, server_default=""),
            sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
            sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
            sa.Column("message_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "gmail_message_id",
                name="uq_email_messages_gmail_message_id",
            ),
        )
        op.create_index("ix_email_messages_lead_id", "email_messages", ["lead_id"])
        op.create_index("ix_email_messages_outreach_id", "email_messages", ["outreach_id"])
        op.create_index(
            "ix_email_messages_gmail_message_id",
            "email_messages",
            ["gmail_message_id"],
        )
        op.create_index(
            "ix_email_messages_gmail_thread_id",
            "email_messages",
            ["gmail_thread_id"],
        )
        op.create_index("ix_email_messages_direction", "email_messages", ["direction"])
        op.create_index("ix_email_messages_message_at", "email_messages", ["message_at"])

    _migrate_legacy_tags(bind)
    _seed_legacy_activity(bind)


def _migrate_legacy_tags(bind: sa.Connection) -> None:
    rows = bind.execute(sa.text("SELECT id, tags FROM leads")).mappings()
    for row in rows:
        raw_tags = row["tags"] or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except json.JSONDecodeError:
                raw_tags = []
        for raw_name in raw_tags if isinstance(raw_tags, list) else []:
            name = str(raw_name).strip()
            if not name:
                continue
            tag_id = bind.execute(
                sa.text("SELECT id FROM crm_tags WHERE name = :name"),
                {"name": name},
            ).scalar_one_or_none()
            if tag_id is None:
                tag_id = str(uuid.uuid4())
                bind.execute(
                    sa.text(
                        "INSERT INTO crm_tags (id, name, color) VALUES (:id, :name, '')"
                    ),
                    {"id": tag_id, "name": name},
                )
            exists = bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM lead_tags
                    WHERE lead_id = :lead_id AND tag_id = :tag_id
                    """
                ),
                {"lead_id": row["id"], "tag_id": tag_id},
            ).first()
            if not exists:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO lead_tags (lead_id, tag_id)
                        VALUES (:lead_id, :tag_id)
                        """
                    ),
                    {"lead_id": row["id"], "tag_id": tag_id},
                )


def _seed_legacy_activity(bind: sa.Connection) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO lead_activities (
                id, lead_id, event_type, title, description, actor, metadata, created_at
            )
            SELECT
                analytics.id,
                analytics.lead_id,
                analytics.event_type,
                CASE analytics.event_type
                    WHEN 'lead_saved' THEN 'Lead generated'
                    WHEN 'email_sent' THEN 'Email sent'
                    WHEN 'email_opened' THEN 'Email opened'
                    WHEN 'email_replied' THEN 'Reply received'
                    ELSE replace(initcap(analytics.event_type), '_', ' ')
                END,
                '',
                'LeadForge AI',
                analytics.metadata,
                analytics.created_at
            FROM analytics
            WHERE analytics.lead_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM lead_activities
                  WHERE lead_activities.id = analytics.id
              )
            """
        )
    )


def downgrade() -> None:
    # CRM migrations preserve production data by design.
    pass
