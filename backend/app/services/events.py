"""Structured event helpers for pipeline and progress reporting."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Analytics


def record_event(
    db: Session,
    event_type: str,
    lead_id: str | None = None,
    campaign_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        Analytics(
            event_type=event_type,
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata_json=metadata or {},
        )
    )
