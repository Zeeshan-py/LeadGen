"""Structured event helpers for pipeline and progress reporting."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Analytics, Campaign, Lead


def record_event(
    db: Session,
    event_type: str,
    lead_id: str | None = None,
    campaign_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> None:
    owner_id = user_id
    if not owner_id and lead_id:
        owner_id = db.scalar(select(Lead.user_id).where(Lead.id == lead_id))
    if not owner_id and campaign_id:
        owner_id = db.scalar(select(Campaign.user_id).where(Campaign.id == campaign_id))
    if not owner_id:
        raise ValueError("Analytics events require a user owner")
    db.add(
        Analytics(
            user_id=owner_id,
            event_type=event_type,
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata_json=metadata or {},
        )
    )
