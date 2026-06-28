from __future__ import annotations

import logging

from lead_automation.apify_maps import ApifyMapsClient
from lead_automation.models import PlaceLead
from lead_automation.validation import qualifies_google_business

from ..config import Settings
from ..schemas import GenerateLeadRequest

logger = logging.getLogger(__name__)


class LeadSkippedNoContact(RuntimeError):
    pass


class LeadSearchService:
    def __init__(self, settings: Settings) -> None:
        self.client = ApifyMapsClient(settings.apify_api_token, settings.apify_actor_id)

    def search(self, payload: GenerateLeadRequest) -> list[PlaceLead]:
        location = ", ".join(
            part for part in (payload.city, payload.country) if part
        )
        leads = self.client.search_one(
            query=payload.business_type,
            location=location,
            max_results=payload.max_leads,
            seen_place_ids=set(),
            website_filter=payload.website_mode,
        )
        logger.info(
            "Lead search completed: raw_leads=%s website_mode=%s",
            len(leads),
            payload.website_mode,
        )
        return leads


class LeadValidationService:
    def eligible_candidates(self, leads: list[PlaceLead]) -> list[PlaceLead]:
        candidates: list[PlaceLead] = []
        for lead in leads:
            eligible = qualifies_google_business(lead)
            logger.info(
                "Lead found: business=%r website_found=%s email_found=%s "
                "phone_found=%s socials_found=%s validation_passed=%s",
                lead.business_name,
                bool(lead.website),
                bool(lead.primary_email()),
                bool(lead.primary_phone()),
                sorted(lead.social_links),
                eligible,
            )
            if eligible:
                candidates.append(lead)
        return candidates

    def ensure_contactable(self, lead: PlaceLead, website_mode: str) -> None:
        contactable = bool(
            lead.primary_email() or lead.social_links or lead.primary_phone()
        )
        logger.info(
            "Contact validation completed: business=%r website_mode=%s "
            "email_found=%s phone_found=%s socials_found=%s contactable=%s",
            lead.business_name,
            website_mode,
            bool(lead.primary_email()),
            bool(lead.primary_phone()),
            sorted(lead.social_links),
            contactable,
        )
        if not contactable:
            raise LeadSkippedNoContact("No email, social profile, or phone number was found")
