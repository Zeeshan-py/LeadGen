from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from lead_automation.models import PlaceLead

from ..ai import OutreachDrafts, WebsiteAnalysis
from ..models import Campaign, Lead, Outreach
from ..schemas import GenerateLeadRequest
from .events import record_event

logger = logging.getLogger(__name__)


class LeadPersistenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(
        self,
        lead: PlaceLead,
        payload: GenerateLeadRequest,
        campaign: Campaign,
        analysis: WebsiteAnalysis,
        outreach: OutreachDrafts,
        screenshot_url: str,
        social_pages: list[str],
    ) -> Lead:
        db_lead = self._upsert_lead(
            lead,
            payload,
            campaign,
            analysis,
            screenshot_url,
            social_pages,
        )
        self._upsert_outreach(db_lead, campaign, outreach)
        record_event(
            self.db,
            "lead_saved",
            lead_id=db_lead.id,
            campaign_id=campaign.id,
            metadata={
                "business_name": db_lead.business_name,
                "opportunity_score": db_lead.opportunity_score,
            },
        )
        self.db.commit()
        logger.info(
            "Persisted lead %s with email confidence %.3f, %s selected social "
            "profiles, and Google Business confidence %.3f",
            lead.business_name,
            lead.email_confidence.get(lead.primary_email(), 0.0),
            len(lead.social_links),
            lead.google_business_confidence,
        )
        return db_lead

    def _upsert_lead(
        self,
        lead: PlaceLead,
        payload: GenerateLeadRequest,
        campaign: Campaign,
        analysis: WebsiteAnalysis,
        screenshot_url: str,
        social_pages: list[str],
    ) -> Lead:
        existing = self.db.scalar(select(Lead).where(Lead.dedupe_key == lead.dedupe_key()))
        row = existing or Lead(
            dedupe_key=lead.dedupe_key(),
            business_name=lead.business_name,
        )
        row.campaign_id = campaign.id
        row.business_name = lead.business_name
        row.website = lead.website
        row.google_maps_url = lead.google_maps_url
        row.email = lead.primary_email()
        row.phone = lead.primary_phone()
        row.location = lead.address
        row.city = lead.city
        row.state = lead.state
        row.country = payload.country
        row.business_type = payload.business_type
        row.website_score = analysis.website_score
        row.opportunity_score = analysis.opportunity_score
        row.website_problems = analysis.website_problems
        row.website_summary = analysis.website_summary
        row.improvement_suggestions = analysis.improvement_suggestions
        row.lead_status = "qualified"
        row.outreach_status = row.outreach_status or "not_started"
        existing_tags = list(row.tags or [])
        row.tags = list(dict.fromkeys([payload.business_type, payload.country, *existing_tags]))
        row.social_links = dict(lead.social_links)
        row.social_status = lead.social_status
        row.screenshot_url = screenshot_url
        row.raw = {
            "place_id": lead.place_id,
            "rating": lead.rating,
            "user_rating_count": lead.user_rating_count,
            "lead_segment": lead.lead_segment,
            "pages_scraped": lead.pages_scraped,
            "social_pages": social_pages,
            "source_notes": lead.source_notes,
            "confidence": {
                "selected_email": {
                    "value": lead.primary_email(),
                    "score": lead.email_confidence.get(lead.primary_email(), 0.0),
                },
                "emails": lead.email_confidence,
                "social_links": lead.social_confidence,
                "google_business": {
                    "value": lead.google_maps_url,
                    "score": lead.google_business_confidence,
                },
            },
        }
        self.db.add(row)
        self.db.flush()
        return row

    def _upsert_outreach(
        self,
        lead: Lead,
        campaign: Campaign,
        drafts: OutreachDrafts,
    ) -> Outreach:
        existing = self.db.scalar(select(Outreach).where(Outreach.lead_id == lead.id))
        row = existing or Outreach(
            lead_id=lead.id,
            campaign_id=campaign.id,
            tracking_id=uuid.uuid4().hex,
        )
        row.campaign_id = campaign.id
        row.subject_line = drafts.subject_line
        row.personalized_first_line = drafts.personalized_first_line
        row.cold_email = drafts.cold_email
        row.follow_up_1 = drafts.follow_up_1
        row.follow_up_2 = drafts.follow_up_2
        self.db.add(row)
        return row
