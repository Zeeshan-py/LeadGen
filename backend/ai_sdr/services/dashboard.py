"""AI SDR dashboard query service.

Provides metrics, filters, contact summaries, single-contact profile data, and
archive semantics for the independent SDR workspace.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ai_sdr.models import AISDRContactRecord
from ai_sdr.schemas import (
    AISDRBulkActionResult,
    AISDRContactSummary,
    AISDRDashboardFilters,
    AISDRDashboardResponse,
    AISDRDashboardStats,
    AISDRSourceType,
)
from app.models import Lead
from app.services.crm import change_crm_stage, record_crm_activity


CALL_READY_STAGES = {"new", "qualified", "interested"}
INTERESTED_STAGES = {"interested", "meeting_scheduled", "won"}
QUALIFIED_STAGES = {"qualified", "email_generated", "email_sent", "opened", "replied"}


class AISDRDashboardService:
    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    def dashboard(
        self,
        *,
        status: str = "",
        industry: str = "",
        city: str = "",
        source: str = "",
        search: str = "",
        limit: int = 200,
        offset: int = 0,
    ) -> AISDRDashboardResponse:
        filters = self._filters(
            status=status,
            industry=industry,
            city=city,
            source=source,
            search=search,
        )
        rows = self.db.execute(
            self._base_query()
            .where(*filters)
            .order_by(Lead.next_follow_up_at.asc().nulls_last(), Lead.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        contacts = [self._summary(lead, record) for lead, record in rows]
        total = int(self.db.scalar(select(func.count(Lead.id)).where(*filters)) or 0)
        return AISDRDashboardResponse(
            stats=self._stats(),
            contacts=contacts,
            filters=self._available_filters(),
            total=total,
        )

    def get_contact(self, contact_id: str) -> AISDRContactSummary | None:
        row = self.db.execute(
            self._base_query()
            .where(Lead.id == contact_id)
            .where(Lead.lead_status != "archived")
            .limit(1)
        ).first()
        if not row:
            return None
        lead, record = row
        return self._summary(lead, record)

    def archive_contacts(self, contact_ids: list[str], *, actor: str) -> AISDRBulkActionResult:
        unique_ids = list(dict.fromkeys(contact_ids))
        leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.id.in_(unique_ids))
                .where(Lead.user_id == self.user_id)
                .where(self._ai_sdr_scope())
            ).all()
        )
        archived_ids: list[str] = []
        for lead in leads:
            if lead.crm_stage != "archived":
                change_crm_stage(
                    self.db,
                    lead,
                    "archived",
                    actor=actor,
                    description="Archived from AI SDR dashboard bulk delete.",
                )
            else:
                lead.lead_status = "archived"
                record_crm_activity(
                    self.db,
                    lead_id=lead.id,
                    event_type="ai_sdr_contact_archived",
                    title="AI SDR contact archived",
                    actor=actor,
                )
            archived_ids.append(lead.id)
        self.db.commit()
        return AISDRBulkActionResult(
            requested=len(unique_ids),
            updated=len(archived_ids),
            skipped=len(unique_ids) - len(archived_ids),
            contact_ids=archived_ids,
        )

    def _base_query(self) -> Select[tuple[Lead, AISDRContactRecord | None]]:
        latest_record_id = (
            select(AISDRContactRecord.id)
            .where(AISDRContactRecord.crm_lead_id == Lead.id)
            .where(AISDRContactRecord.user_id == self.user_id)
            .order_by(AISDRContactRecord.created_at.desc(), AISDRContactRecord.updated_at.desc())
            .limit(1)
            .correlate(Lead)
            .scalar_subquery()
        )
        return (
            select(Lead, AISDRContactRecord)
            .join(
                AISDRContactRecord,
                AISDRContactRecord.id == latest_record_id,
                isouter=True,
            )
            .where(self._ai_sdr_scope())
            .where(Lead.user_id == self.user_id)
        )

    def _ai_sdr_scope(self) -> Any:
        return or_(
            Lead.source == "ai_sdr",
            Lead.id.in_(
                select(AISDRContactRecord.crm_lead_id).where(
                    AISDRContactRecord.user_id == self.user_id,
                    AISDRContactRecord.crm_lead_id.is_not(None),
                )
            ),
        )

    def _filters(
        self,
        *,
        status: str,
        industry: str,
        city: str,
        source: str,
        search: str,
    ) -> list[Any]:
        filters: list[Any] = [Lead.user_id == self.user_id, self._ai_sdr_scope()]
        if status:
            filters.append(Lead.lead_status == status)
        else:
            filters.append(Lead.lead_status != "archived")
        if industry:
            filters.append(Lead.business_type == industry)
        if city:
            filters.append(Lead.city == city)
        if source:
            filters.append(
                or_(
                    Lead.source == source,
                    Lead.id.in_(
                        select(AISDRContactRecord.crm_lead_id).where(
                            AISDRContactRecord.user_id == self.user_id,
                            AISDRContactRecord.source_type == source,
                        )
                    ),
                )
            )
        if search.strip():
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    Lead.business_name.ilike(like),
                    Lead.contact_name.ilike(like),
                    Lead.email.ilike(like),
                    Lead.phone.ilike(like),
                    Lead.city.ilike(like),
                    Lead.business_type.ilike(like),
                )
            )
        return filters

    def _stats(self) -> AISDRDashboardStats:
        leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.user_id == self.user_id)
                .where(self._ai_sdr_scope())
                .where(Lead.lead_status != "archived")
            ).all()
        )
        total = len(leads)
        ready = sum(1 for lead in leads if lead.phone and lead.crm_stage in CALL_READY_STAGES)
        interested = sum(1 for lead in leads if lead.crm_stage in INTERESTED_STAGES)
        qualified = sum(1 for lead in leads if lead.crm_stage in QUALIFIED_STAGES)
        meetings = sum(1 for lead in leads if lead.crm_stage == "meeting_scheduled")
        conversion_rate = round((interested / total) * 100, 1) if total else 0.0
        return AISDRDashboardStats(
            total_contacts=total,
            ready_to_call=ready,
            calls_today=0,
            interested=interested,
            qualified=qualified,
            meetings_pending=meetings,
            average_call_duration_seconds=0,
            conversion_rate=conversion_rate,
        )

    def _available_filters(self) -> AISDRDashboardFilters:
        leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.user_id == self.user_id)
                .where(self._ai_sdr_scope())
                .where(Lead.lead_status != "archived")
            ).all()
        )
        sources = {
            str(row)
            for row in self.db.scalars(
                select(AISDRContactRecord.source_type)
                .where(AISDRContactRecord.user_id == self.user_id)
                .where(AISDRContactRecord.crm_lead_id.is_not(None))
                .distinct()
            ).all()
            if row
        }
        sources.update(lead.source for lead in leads if lead.source)
        if not sources:
            sources = {source.value for source in AISDRSourceType}
        return AISDRDashboardFilters(
            statuses=sorted({lead.lead_status for lead in leads if lead.lead_status}),
            industries=sorted({lead.business_type for lead in leads if lead.business_type}),
            cities=sorted({lead.city for lead in leads if lead.city}),
            sources=sorted(sources),
        )

    @staticmethod
    def _summary(lead: Lead, record: AISDRContactRecord | None) -> AISDRContactSummary:
        source = record.source_type if record else lead.source
        return AISDRContactSummary(
            id=lead.id,
            company=lead.business_name,
            contact=lead.contact_name,
            phone=lead.phone,
            email=lead.email,
            industry=lead.business_type,
            status=lead.lead_status,
            source=source or "ai_sdr",
            pipeline_stage=lead.crm_stage,
            next_follow_up=lead.next_follow_up_at,
            city=lead.city,
            state=lead.state,
            country=lead.country,
            website=lead.website,
            notes=lead.notes,
            last_contacted_at=lead.last_contacted_at,
            source_record_id=record.id if record else None,
            source_batch_id=record.batch_id if record else None,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
