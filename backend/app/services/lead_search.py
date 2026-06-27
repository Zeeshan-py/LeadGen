from __future__ import annotations

from lead_automation.apify_maps import ApifyMapsClient
from lead_automation.models import PlaceLead
from lead_automation.validation import qualifies_google_business

from ..config import Settings
from ..schemas import GenerateLeadRequest


class LeadSkippedNoContact(RuntimeError):
    pass


class LeadSearchService:
    def __init__(self, settings: Settings) -> None:
        self.client = ApifyMapsClient(settings.apify_api_token, settings.apify_actor_id)

    def search(self, payload: GenerateLeadRequest) -> list[PlaceLead]:
        return self.client.search_one(
            query=payload.business_type,
            location=payload.country,
            max_results=payload.max_leads,
            seen_place_ids=set(),
            website_filter=payload.website_mode,
        )


class LeadValidationService:
    def eligible_candidates(self, leads: list[PlaceLead]) -> list[PlaceLead]:
        return [lead for lead in leads if qualifies_google_business(lead)]

    def ensure_contactable(self, lead: PlaceLead, website_mode: str) -> None:
        if not (lead.primary_email() or lead.social_links or lead.primary_phone()):
            raise LeadSkippedNoContact("No email, social profile, or phone number was found")
