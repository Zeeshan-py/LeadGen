"""Regression tests for outreach generation, Gmail sending, and email sync."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from app.ai import OutreachDrafts, WebsiteAnalysis
from app.config import Settings
from app.gmail import (
    GmailClient,
    GmailConfigurationError,
    GmailSendError,
)
from app.schemas import GenerateLeadRequest
from app.services.lead_analysis import LeadAnalysisService
from app.services.lead_search import LeadSearchService
from lead_automation.models import PlaceLead


class FailingOutreachAI:
    def __init__(self) -> None:
        self.calls = 0

    def generate_outreach(
        self,
        lead: PlaceLead,
        business_type: str,
        analysis: WebsiteAnalysis,
    ) -> OutreachDrafts:
        self.calls += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")


class RetryOutreachAI:
    def __init__(self) -> None:
        self.calls = 0

    def generate_outreach(
        self,
        lead: PlaceLead,
        business_type: str,
        analysis: WebsiteAnalysis,
    ) -> OutreachDrafts:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return OutreachDrafts(
            "Subject",
            "Personalized first line",
            "Personalized cold email",
            "Follow up one",
            "Follow up two",
        )


class CapturingMapsClient:
    def __init__(self) -> None:
        self.location = ""

    def search_one(self, **kwargs: object) -> list[PlaceLead]:
        self.location = str(kwargs["location"])
        return []


class OutreachAndEmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lead = PlaceLead(
            business_name="Acme Dental",
            city="Dallas",
            address="100 Main Street, Dallas, TX",
            email="hello@acmedental.test",
        )
        self.analysis = WebsiteAnalysis(
            website_score=0,
            opportunity_score=80,
            website_problems=["No valid website found"],
            website_summary="No website was available.",
            improvement_suggestions=[],
        )

    def test_ai_outreach_retries_once_then_returns_personalized_fallback(self) -> None:
        ai = FailingOutreachAI()
        service = LeadAnalysisService(ai=ai, contact_extractor=None)

        drafts = service.generate_outreach(
            self.lead,
            "Dentists",
            self.analysis,
        )

        self.assertEqual(ai.calls, 2)
        self.assertIn("Acme Dental", drafts.cold_email)
        self.assertIn("Dallas", drafts.personalized_first_line)
        self.assertTrue(drafts.subject_line)
        self.assertIn("quota", drafts.generation_error.lower())

    def test_ai_outreach_uses_successful_second_attempt(self) -> None:
        ai = RetryOutreachAI()
        service = LeadAnalysisService(ai=ai, contact_extractor=None)

        drafts = service.generate_outreach(
            self.lead,
            "Dentists",
            self.analysis,
        )

        self.assertEqual(ai.calls, 2)
        self.assertEqual(drafts.cold_email, "Personalized cold email")
        self.assertEqual(drafts.generation_error, "")

    def test_city_is_added_to_maps_search_location(self) -> None:
        service = LeadSearchService(Settings(APIFY_API_TOKEN="test-token"))
        client = CapturingMapsClient()
        service.client = client
        payload = GenerateLeadRequest(
            continent="North America",
            country="United States",
            city="Dallas",
            business_type="Dentists",
            max_leads=10,
            website_mode="withWebsite",
        )

        service.search(payload)

        self.assertEqual(client.location, "Dallas, United States")

    @patch("app.gmail.Credentials")
    def test_invalid_refresh_token_returns_clear_configuration_error(
        self,
        credentials_class: MagicMock,
    ) -> None:
        credentials_class.return_value.refresh.side_effect = RefreshError(
            "invalid_grant"
        )

        with self.assertRaisesRegex(
            GmailConfigurationError,
            "invalid or expired",
        ):
            GmailClient(
                "client-id",
                "client-secret",
                "expired-refresh-token",
                "sender@example.test",
            )

    def test_gmail_send_wraps_provider_error(self) -> None:
        client = object.__new__(GmailClient)
        client.sender_email = "sender@example.test"
        client.profile_email = "sender@example.test"
        client.service = MagicMock()
        client.service.users.return_value.messages.return_value.send.return_value.execute.side_effect = (
            RuntimeError("provider detail")
        )

        with self.assertRaisesRegex(
            GmailSendError,
            "could not send",
        ):
            client.send_email(
                "recipient@example.test",
                "Subject",
                "Body",
            )


if __name__ == "__main__":
    unittest.main()
