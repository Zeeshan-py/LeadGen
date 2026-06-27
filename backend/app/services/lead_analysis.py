from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from lead_automation.ai_extractor import LeadExtractor
from lead_automation.models import PlaceLead

from ..ai import GeminiLeadAI, OutreachDrafts, WebsiteAnalysis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeadAnalysisResult:
    website: WebsiteAnalysis
    outreach: OutreachDrafts


class LeadAnalysisService:
    def __init__(
        self,
        ai: GeminiLeadAI | None,
        contact_extractor: LeadExtractor | None,
    ) -> None:
        self.ai = ai
        self.contact_extractor = contact_extractor

    def enrich_structured_contact(self, lead: PlaceLead) -> None:
        if not self.contact_extractor or not lead.website:
            return
        extracted = self.contact_extractor.extract(lead)
        lead.merge_extracted(extracted)
        if lead.enrichment_status == "website_crawled":
            lead.enrichment_status = "ai_enriched"

    def analyze_website(
        self,
        lead: PlaceLead,
        business_type: str,
        crawl: dict[str, Any],
    ) -> WebsiteAnalysis:
        has_website = bool(lead.website and crawl.get("website_valid", True))
        if self.ai and has_website:
            try:
                return self.ai.analyze_website(lead, business_type, crawl)
            except Exception as exc:
                _log_ai_failure("website analysis", lead.business_name, exc)
        elif not has_website:
            logger.info(
                "Using no-website AI analysis fallback for %s after contact enrichment",
                lead.business_name,
            )
        return WebsiteAnalysis(
            website_score=50 if has_website else 0,
            opportunity_score=50 if has_website else 80,
            website_problems=[] if has_website else ["No valid website found"],
            website_summary=(
                "Website was crawled; AI analysis was unavailable."
                if has_website
                else "No valid website was available."
            ),
            improvement_suggestions=[],
        )

    def generate_outreach(
        self,
        lead: PlaceLead,
        business_type: str,
        analysis: WebsiteAnalysis,
    ) -> OutreachDrafts:
        if self.ai:
            try:
                return self.ai.generate_outreach(lead, business_type, analysis)
            except Exception as exc:
                _log_ai_failure("outreach generation", lead.business_name, exc)
        return OutreachDrafts("", "", "", "", "")


def _log_ai_failure(operation: str, business_name: str, exc: Exception) -> None:
    message = str(exc).lower()
    if any(
        marker in message
        for marker in ("429", "resource_exhausted", "quota", "rate limit")
    ):
        logger.warning(
            "AI %s skipped for %s because the configured quota is unavailable",
            operation,
            business_name,
        )
        return
    logger.exception("AI %s failed for %s", operation, business_name)
