"""CRM gateway for AI SDR.

This is the only AI SDR infrastructure boundary that writes normalized SDR
contacts into the shared CRM tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ai_sdr.config import get_ai_sdr_settings
from ai_sdr.services.normalization import NormalizedContact, domain_from_url
from app.models import Lead
from app.services.crm import record_crm_activity, replace_lead_tags


@dataclass(frozen=True)
class AISDRCRMResult:
    lead: Lead
    created: bool


class AISDRCRMGateway:
    """Writes normalized AI SDR contacts to the shared CRM boundary."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_ai_sdr_settings()

    def upsert_contact(
        self,
        contact: NormalizedContact,
        *,
        batch_id: str,
        record_id: str,
        actor: str,
    ) -> AISDRCRMResult:
        existing = self._find_existing(contact)
        created = existing is None
        lead = existing or Lead(
            dedupe_key=contact.dedupe_key,
            business_name=contact.business_name,
            lead_status=self.settings.default_crm_stage,
            crm_stage=self.settings.default_crm_stage,
            outreach_status="not_started",
            source="ai_sdr",
        )
        self._apply_contact(lead, contact, created=created)
        self.db.add(lead)
        self.db.flush()

        merged_tags = list(dict.fromkeys([*(lead.tags or []), *contact.tags]))
        replace_lead_tags(self.db, lead, merged_tags, actor=actor)
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_contact_stored" if created else "ai_sdr_contact_merged",
            title="AI SDR contact stored" if created else "AI SDR contact merged",
            description=contact.business_name,
            actor=actor,
            metadata={
                "batch_id": batch_id,
                "record_id": record_id,
                "source_type": contact.source_type,
                "external_id": contact.external_id,
                "dedupe_key": contact.dedupe_key,
            },
        )
        return AISDRCRMResult(lead=lead, created=created)

    def _find_existing(self, contact: NormalizedContact) -> Lead | None:
        filters: list[Any] = [Lead.dedupe_key == contact.dedupe_key]
        if contact.email:
            filters.append(func.lower(Lead.email) == contact.email)
        if contact.website:
            filters.append(Lead.website == contact.website)
            domain = domain_from_url(contact.website)
            if domain:
                filters.append(Lead.dedupe_key == f"domain:{domain}")
        if contact.phone:
            filters.append(Lead.phone == contact.phone)
        return self.db.scalar(select(Lead).where(or_(*filters)).limit(1))

    def _apply_contact(self, lead: Lead, contact: NormalizedContact, *, created: bool) -> None:
        if created or not lead.business_name:
            lead.business_name = contact.business_name
        self._fill(lead, "contact_name", contact.contact_name)
        self._fill(lead, "email", contact.email)
        self._fill(lead, "phone", contact.phone)
        self._fill(lead, "website", contact.website)
        self._fill(lead, "location", contact.address)
        self._fill(lead, "city", contact.city)
        self._fill(lead, "state", contact.state)
        self._fill(lead, "country", contact.country)
        self._fill(lead, "business_type", contact.industry)
        if contact.notes and not lead.notes:
            lead.notes = contact.notes
        lead.source = lead.source or "ai_sdr"
        lead.raw = {
            **(lead.raw or {}),
            "ai_sdr": {
                "source_type": contact.source_type,
                "external_id": contact.external_id,
                "title": contact.title,
                "linkedin_url": contact.linkedin_url,
                "raw": contact.raw,
            },
        }

    @staticmethod
    def _fill(lead: Lead, field_name: str, value: str) -> None:
        if value and not getattr(lead, field_name):
            setattr(lead, field_name, value)
