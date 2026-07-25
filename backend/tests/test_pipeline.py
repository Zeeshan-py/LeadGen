"""Regression tests for the lead generation pipeline."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai import OutreachDrafts, WebsiteAnalysis
from app.config import Settings
from app.database import Base
from app.models import Campaign, Lead, Outreach
from app.schemas import GenerateLeadRequest
from app.services.lead_analysis import LeadAnalysisService
from app.services.lead_pipeline import LeadPipeline
from app.services.lead_search import LeadValidationService
from lead_automation.contact_discovery import ContactDiscoveryResult
from lead_automation.models import PlaceLead
from tests import TEST_USER_ID


class FakeScraper:
    def crawl(self, url: str) -> dict[str, object]:
        return {
            "text": "Acme provides dental services. Contact hello@acme.example.",
            "emails": ["hello@acme.example"],
            "phones": ["+15551234567"],
            "pages_scraped": 1,
            "social_links": {"facebook": ["https://facebook.com/acme-dental"]},
            "social_pages": ["homepage"],
            "email_sources": {
                "hello@acme.example": ["homepage:https://acme.example/"],
            },
            "phone_sources": {
                "+15551234567": ["homepage:https://acme.example/"],
            },
            "social_link_sources": {
                "facebook": {
                    "https://facebook.com/acme-dental": ["homepage:footer:href"],
                }
            },
            "website_valid": True,
        }


class FakeAI:
    def __init__(self) -> None:
        self.analysis_calls = 0
        self.outreach_calls = 0

    def analyze_website(
        self,
        lead: PlaceLead,
        business_type: str,
        crawl: dict[str, object],
    ) -> WebsiteAnalysis:
        self.analysis_calls += 1
        return WebsiteAnalysis(70, 80, ["Issue"], "Summary", ["Suggestion"])

    def generate_outreach(
        self,
        lead: PlaceLead,
        business_type: str,
        analysis: WebsiteAnalysis,
    ) -> OutreachDrafts:
        self.outreach_calls += 1
        return OutreachDrafts("Subject", "First line", "Email", "Follow up 1", "Follow up 2")


class FakeNoWebsiteDiscovery:
    def __init__(self, result: ContactDiscoveryResult | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.result = result or ContactDiscoveryResult()

    def search_business(self, *args: object, **kwargs: object) -> ContactDiscoveryResult:
        self.calls.append(kwargs)
        return self.result


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_pipeline_runs_each_stage_once_and_saves_lead(self) -> None:
        settings = Settings(
            ENABLE_CONTACT_DISCOVERY=False,
            ENABLE_SCREENSHOT_CAPTURE=False,
        )
        ai = FakeAI()
        stages: list[str] = []
        payload = GenerateLeadRequest(
            continent="North America",
            country="United States",
            business_type="Dentists",
            max_leads=1,
            website_mode="withWebsite",
        )

        with Session(self.engine, expire_on_commit=False) as db:
            campaign = Campaign(
                name="US Dentists",
                country="United States",
                continent="North America",
                business_type="Dentists",
                status="running",
                max_leads=1,
            )
            db.add(campaign)
            db.commit()
            pipeline = LeadPipeline(
                db=db,
                settings=settings,
                scraper=FakeScraper(),
                ai=ai,
                contact_extractor=None,
                validation=LeadValidationService(),
                user_id=TEST_USER_ID,
            )
            lead = PlaceLead(
                place_id="place-1",
                business_name="Acme Dental",
                website="https://acme.example",
            )

            pipeline.process(
                lead,
                payload,
                campaign,
                base_progress=14,
                report_progress=lambda stage, _progress: stages.append(stage),
            )

            saved = db.scalar(select(Lead).where(Lead.dedupe_key == "pid:place-1"))
            outreach = db.scalar(select(Outreach).where(Outreach.lead_id == saved.id))

        self.assertEqual(
            stages,
            [
                "Scraping Websites",
                "Finding Emails",
                "Finding Phone Numbers",
                "Analyzing Websites",
                "Generating AI Insights",
                "Creating Personalized Outreach",
                "Saving Leads",
            ],
        )
        self.assertEqual(ai.analysis_calls, 1)
        self.assertEqual(ai.outreach_calls, 1)
        self.assertEqual(saved.email, "hello@acme.example")
        self.assertEqual(saved.social_links["facebook"], "https://facebook.com/acme-dental")
        self.assertEqual(
            saved.raw["confidence"]["emails"]["hello@acme.example"],
            0.99,
        )
        self.assertEqual(
            saved.raw["confidence"]["social_links"]["facebook"][
                "https://facebook.com/acme-dental"
            ],
            0.98,
        )
        self.assertEqual(outreach.subject_line, "Subject")

    def test_no_website_uses_fallback_without_gemini_analysis_call(self) -> None:
        ai = FakeAI()
        service = LeadAnalysisService(ai=ai, contact_extractor=None)
        lead = PlaceLead(business_name="No Site Business")

        analysis = service.analyze_website(lead, "Dentists", {"website_valid": False})
        service.generate_outreach(lead, "Dentists", analysis)

        self.assertEqual(ai.analysis_calls, 0)
        self.assertEqual(ai.outreach_calls, 1)
        self.assertEqual(analysis.website_score, 0)
        self.assertEqual(analysis.opportunity_score, 80)

    def test_phone_only_no_website_lead_is_enriched_analyzed_and_saved(self) -> None:
        settings = Settings(
            ENABLE_CONTACT_DISCOVERY=True,
            ENABLE_SCREENSHOT_CAPTURE=False,
        )
        ai = FakeAI()
        discovery = FakeNoWebsiteDiscovery()
        payload = GenerateLeadRequest(
            continent="North America",
            country="United States",
            business_type="Pet Groomers",
            max_leads=1,
            website_mode="withoutWebsite",
        )

        with Session(self.engine, expire_on_commit=False) as db:
            campaign = Campaign(
                name="No Website Leads",
                country="United States",
                continent="North America",
                business_type="Pet Groomers",
                status="running",
                max_leads=1,
            )
            db.add(campaign)
            db.commit()
            pipeline = LeadPipeline(
                db=db,
                settings=settings,
                scraper=FakeScraper(),
                ai=ai,
                contact_extractor=None,
                validation=LeadValidationService(),
                user_id=TEST_USER_ID,
            )
            pipeline.contact_enrichment.discovery = discovery
            lead = PlaceLead(
                place_id="phone-only",
                business_name="Phone Only Groomer",
                address="100 Main Street, Dallas, TX",
                city="Dallas",
                state="TX",
                country="United States",
                phone="+12145550199",
            )

            pipeline.process(
                lead,
                payload,
                campaign,
                base_progress=14,
                report_progress=lambda _stage, _progress: None,
            )
            saved = db.scalar(
                select(Lead).where(Lead.dedupe_key == "pid:phone-only")
            )

        self.assertIsNotNone(saved)
        self.assertEqual(saved.phone, "+12145550199")
        self.assertEqual(saved.website, "")
        self.assertEqual(ai.analysis_calls, 0)
        self.assertEqual(ai.outreach_calls, 1)
        self.assertEqual(len(discovery.calls), 1)
        self.assertTrue(discovery.calls[0]["exhaustive"])

    def test_no_website_discovered_contacts_survive_validation_and_save(self) -> None:
        settings = Settings(
            ENABLE_CONTACT_DISCOVERY=True,
            ENABLE_SCREENSHOT_CAPTURE=False,
        )
        email = "hello@no-site.example"
        facebook = "https://facebook.com/no-site-groomer-dallas"
        discovery = FakeNoWebsiteDiscovery(
            ContactDiscoveryResult(
                emails=[email],
                social_links={"facebook": [facebook]},
                email_sources={email: ["duckduckgo:email:example.com"]},
                social_sources={
                    "facebook": {
                        facebook: ["duckduckgo:social_primary:facebook.com"]
                    }
                },
                email_confidence={email: 0.91},
                social_confidence={"facebook": {facebook: 0.94}},
            )
        )
        payload = GenerateLeadRequest(
            continent="North America",
            country="United States",
            business_type="Pet Groomers",
            max_leads=1,
            website_mode="withoutWebsite",
        )

        with Session(self.engine, expire_on_commit=False) as db:
            campaign = Campaign(
                name="No Website Contacts",
                country="United States",
                continent="North America",
                business_type="Pet Groomers",
                status="running",
                max_leads=1,
            )
            db.add(campaign)
            db.commit()
            pipeline = LeadPipeline(
                db=db,
                settings=settings,
                scraper=FakeScraper(),
                ai=FakeAI(),
                contact_extractor=None,
                validation=LeadValidationService(),
                user_id=TEST_USER_ID,
            )
            pipeline.contact_enrichment.discovery = discovery
            lead = PlaceLead(
                place_id="no-site-contacts",
                business_name="No Site Groomer",
                address="100 Main Street, Dallas, TX",
                city="Dallas",
                state="TX",
                country="United States",
                phone="+12145550199",
            )

            pipeline.process(
                lead,
                payload,
                campaign,
                base_progress=14,
                report_progress=lambda _stage, _progress: None,
            )
            saved = db.scalar(
                select(Lead).where(Lead.dedupe_key == "pid:no-site-contacts")
            )

        self.assertEqual(saved.email, email)
        self.assertEqual(saved.social_links, {"facebook": facebook})
        self.assertEqual(saved.social_status, "found")
        self.assertEqual(saved.raw["confidence"]["emails"][email], 0.91)
        self.assertEqual(
            saved.raw["confidence"]["social_links"]["facebook"][facebook],
            0.94,
        )


if __name__ == "__main__":
    unittest.main()
