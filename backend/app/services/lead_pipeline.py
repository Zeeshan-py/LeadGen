"""Lead generation pipeline service.

Coordinates source discovery, website enrichment, AI analysis, and persistence
steps used by background generation jobs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from lead_automation.ai_extractor import LeadExtractor
from lead_automation.models import PlaceLead
from lead_automation.website_scraper import WebsiteScraper

from ..ai import GeminiLeadAI
from ..config import Settings
from ..models import Campaign, Lead
from ..schemas import GenerateLeadRequest
from ..screenshots import capture_website_screenshot
from .contact_enrichment import (
    ContactEnrichmentService,
    ContactEvidenceRecorder,
    SocialEnrichmentService,
)
from .lead_analysis import LeadAnalysisResult, LeadAnalysisService
from .lead_persistence import LeadPersistenceService
from .lead_search import LeadValidationService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int], None]


class LeadPipeline:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        scraper: WebsiteScraper,
        ai: GeminiLeadAI | None,
        contact_extractor: LeadExtractor | None,
        validation: LeadValidationService,
    ) -> None:
        evidence = ContactEvidenceRecorder()
        self.settings = settings
        self.contact_enrichment = ContactEnrichmentService(scraper, settings, evidence)
        self.social_enrichment = SocialEnrichmentService(evidence)
        self.analysis = LeadAnalysisService(ai, contact_extractor)
        self.validation = validation
        self.persistence = LeadPersistenceService(db)

    def process(
        self,
        lead: PlaceLead,
        payload: GenerateLeadRequest,
        campaign: Campaign,
        base_progress: int,
        report_progress: ProgressCallback,
    ) -> Lead:
        lead.coverage_market = campaign.name
        lead.search_query = payload.business_type
        logger.info(
            "Pipeline started: business=%r website_found=%s maps_url_found=%s "
            "email_found=%s phone_found=%s socials_found=%s",
            lead.business_name,
            bool(lead.website),
            bool(lead.google_maps_url),
            bool(lead.primary_email()),
            bool(lead.primary_phone()),
            sorted(lead.social_links),
        )

        report_progress("Scraping Websites", min(90, base_progress + 2))
        enrichment = self.contact_enrichment.enrich(lead, payload)

        report_progress("Finding Emails", min(91, base_progress + 4))
        report_progress("Finding Phone Numbers", min(92, base_progress + 5))
        self.social_enrichment.enrich(
            lead,
            enrichment.social_candidates,
            enrichment.crawl,
        )

        self.analysis.enrich_structured_contact(lead)
        self.validation.ensure_contactable(lead, payload.website_mode)
        logger.info(
            "Enrichment stages completed: business=%r email=%r phone=%r socials=%s",
            lead.business_name,
            lead.primary_email(),
            lead.primary_phone(),
            lead.social_links,
        )

        report_progress("Analyzing Websites", min(93, base_progress + 6))
        logger.info(
            "AI analysis started: business=%r website_found=%s",
            lead.business_name,
            bool(lead.website),
        )
        website_analysis = self.analysis.analyze_website(
            lead,
            payload.business_type,
            enrichment.crawl,
        )

        report_progress("Generating AI Insights", min(94, base_progress + 7))
        outreach = self.analysis.generate_outreach(
            lead,
            payload.business_type,
            website_analysis,
        )
        analysis_result = LeadAnalysisResult(
            website=website_analysis,
            outreach=outreach,
        )

        screenshot_url = self._capture_screenshot(lead)

        report_progress("Creating Personalized Outreach", min(95, base_progress + 8))
        saved = self.persistence.save(
            lead=lead,
            payload=payload,
            campaign=campaign,
            analysis=analysis_result.website,
            outreach=analysis_result.outreach,
            screenshot_url=screenshot_url,
            social_pages=list(enrichment.crawl.get("social_pages", [])),
        )
        logger.info(
            "Pipeline completed: business=%r database_save_completed=Yes lead_id=%s",
            lead.business_name,
            saved.id,
        )
        report_progress("Saving Leads", min(98, base_progress + 10))
        return saved

    def _capture_screenshot(self, lead: PlaceLead) -> str:
        if not self.settings.enable_screenshot_capture or not lead.website:
            return ""
        try:
            return capture_website_screenshot(
                lead.website,
                self.settings.screenshots_dir,
                self.settings.public_backend_url,
            )
        except Exception:
            logger.exception("Website screenshot capture failed for %s", lead.business_name)
            return ""
