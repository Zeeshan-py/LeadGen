"""Shared CRM mutation helpers.

Use these helpers for stage transitions, activity records, tags, and contacted
timestamps so all modules leave consistent audit trails in the CRM timeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CrmTag, Lead, LeadActivity, LeadTag

CRM_STAGES = (
    "new",
    "qualified",
    "email_generated",
    "email_sent",
    "opened",
    "replied",
    "interested",
    "meeting_scheduled",
    "won",
    "lost",
    "archived",
)

STAGE_LABELS = {
    "new": "New",
    "qualified": "Qualified",
    "email_generated": "Email Generated",
    "email_sent": "Email Sent",
    "opened": "Opened",
    "replied": "Replied",
    "interested": "Interested",
    "meeting_scheduled": "Meeting Scheduled",
    "won": "Won",
    "lost": "Lost",
    "archived": "Archived",
}


def record_crm_activity(
    db: Session,
    *,
    lead_id: str,
    event_type: str,
    title: str,
    description: str = "",
    actor: str = "LeadForge AI",
    metadata: dict[str, Any] | None = None,
) -> LeadActivity:
    activity = LeadActivity(
        lead_id=lead_id,
        event_type=event_type,
        title=title,
        description=description,
        actor=actor,
        metadata_json=metadata or {},
    )
    db.add(activity)
    return activity


def change_crm_stage(
    db: Session,
    lead: Lead,
    stage: str,
    *,
    actor: str = "LeadForge user",
    description: str = "",
) -> bool:
    if stage not in CRM_STAGES:
        raise ValueError(f"Unsupported CRM stage: {stage}")
    previous = lead.crm_stage
    if previous == stage:
        return False
    lead.crm_stage = stage
    lead.lead_status = stage
    record_crm_activity(
        db,
        lead_id=lead.id,
        event_type="status_changed",
        title=f"Status changed to {STAGE_LABELS[stage]}",
        description=description,
        actor=actor,
        metadata={"from": previous, "to": stage},
    )
    return True


def replace_lead_tags(
    db: Session,
    lead: Lead,
    names: list[str],
    *,
    actor: str = "LeadForge user",
) -> list[CrmTag]:
    normalized = list(
        dict.fromkeys(" ".join(name.strip().split())[:80] for name in names if name.strip())
    )
    existing_tags = {
        tag.name: tag
        for tag in db.scalars(select(CrmTag).where(CrmTag.name.in_(normalized))).all()
    } if normalized else {}
    tags: list[CrmTag] = []
    for name in normalized:
        tag = existing_tags.get(name)
        if tag is None:
            tag = CrmTag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)

    lead.crm_tag_links.clear()
    db.flush()
    for tag in tags:
        lead.crm_tag_links.append(LeadTag(tag=tag))
    lead.tags = normalized
    record_crm_activity(
        db,
        lead_id=lead.id,
        event_type="tags_updated",
        title="Tags updated",
        description=", ".join(normalized) if normalized else "All tags removed",
        actor=actor,
        metadata={"tags": normalized},
    )
    return tags


def mark_contacted(lead: Lead, at: datetime | None = None) -> datetime:
    contacted_at = at or datetime.now(timezone.utc)
    lead.last_contacted_at = contacted_at
    return contacted_at
