from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from lead_automation.confidence import HIGH_CONFIDENCE_THRESHOLD, confidence_label
from lead_automation.contact_discovery import ContactDiscovery, ContactDiscoveryResult
from lead_automation.models import PlaceLead, merge_unique
from lead_automation.social_links import (
    SOCIAL_NETWORKS,
    merge_social_candidates,
    merged_social_candidates,
    select_social_links,
    social_network_for_url,
)
from lead_automation.source_maps import (
    merged_social_source_maps,
    merged_source_maps,
    normalize_social_source_map,
    normalize_source_map,
)
from lead_automation.validation import normalize_website
from lead_automation.website_scraper import WebsiteScraper

from ..config import Settings
from ..schemas import GenerateLeadRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContactEnrichmentResult:
    crawl: dict[str, Any]
    social_candidates: dict[str, list[str]]


class ContactEvidenceRecorder:
    def record_initial(self, lead: PlaceLead) -> None:
        for email in [lead.email, *lead.raw_emails]:
            if email:
                self._record(
                    lead,
                    "email",
                    email,
                    ["apify_google_maps"],
                    confidence=0.95,
                )
        for phone in [lead.phone, *lead.raw_phones]:
            if phone:
                self._record(lead, "phone", phone, ["apify_google_maps"])
        for network, link in (lead.social_links or {}).items():
            if link:
                self._record(
                    lead,
                    network,
                    link,
                    ["apify_google_maps"],
                    confidence=0.93,
                )
        if lead.google_maps_url:
            lead.google_business_confidence = max(
                lead.google_business_confidence,
                0.99,
            )
            self._record(
                lead,
                "google_business",
                lead.google_maps_url,
                ["apify_google_maps"],
                confidence=0.99,
            )

    def record_crawl(self, lead: PlaceLead, crawl: dict[str, Any]) -> None:
        for email, sources in normalize_source_map(crawl.get("email_sources", {})).items():
            self._record(
                lead,
                "email",
                email,
                sources,
                confidence=_website_email_confidence(email, lead.website),
            )
        for phone, sources in normalize_source_map(crawl.get("phone_sources", {})).items():
            self._record(lead, "phone", phone, sources)
        self._record_social_sources(
            lead,
            normalize_social_source_map(crawl.get("social_link_sources", {})),
            default_confidence=0.98,
        )

    def record_discovery(self, lead: PlaceLead, result: ContactDiscoveryResult) -> None:
        for email, sources in normalize_source_map(result.email_sources).items():
            self._record(
                lead,
                "email",
                email,
                sources,
                confidence=result.email_confidence.get(email, 0.0),
            )
        for phone, sources in normalize_source_map(result.phone_sources).items():
            self._record(lead, "phone", phone, sources)
        self._record_social_sources(
            lead,
            normalize_social_source_map(result.social_sources),
            confidence=result.social_confidence,
        )
        for link, sources in normalize_source_map(
            result.google_business_sources
        ).items():
            self._record(
                lead,
                "google_business",
                link,
                sources,
                confidence=result.google_business_confidence.get(link, 0.0),
            )

    def record_verified_social(self, lead: PlaceLead, crawl: dict[str, Any]) -> None:
        source_map = normalize_social_source_map(crawl.get("social_link_sources", {}))
        for network, link in (lead.social_links or {}).items():
            sources = source_map.get(network, {}).get(link, [])
            self._record(
                lead,
                f"verified_{network}",
                link,
                sources or ["verified_existing_candidate"],
                confidence=lead.social_confidence.get(network, {}).get(link, 0.0),
            )

    def _record_social_sources(
        self,
        lead: PlaceLead,
        source_map: dict[str, dict[str, list[str]]],
        confidence: dict[str, dict[str, float]] | None = None,
        default_confidence: float = 0.0,
    ) -> None:
        for network, links in source_map.items():
            for link, sources in links.items():
                self._record(
                    lead,
                    network,
                    link,
                    sources,
                    confidence=(confidence or {}).get(network, {}).get(
                        link,
                        default_confidence,
                    ),
                )

    def record_social_candidate(
        self,
        lead: PlaceLead,
        network: str,
        value: str,
        source: str,
        confidence: float,
    ) -> None:
        self._record(
            lead,
            network,
            value,
            [source],
            confidence=confidence,
        )

    def _record(
        self,
        lead: PlaceLead,
        contact_type: str,
        value: str,
        sources: list[str],
        confidence: float | None = None,
    ) -> None:
        clean_sources = list(dict.fromkeys(source for source in sources if source))
        source_text = ", ".join(clean_sources) or "unknown_source"
        if contact_type == "email" and confidence is not None:
            lead.record_email_confidence(value, confidence)
        elif contact_type in SOCIAL_NETWORKS:
            if confidence is not None:
                lead.record_social_confidence(contact_type, value, confidence)
        elif contact_type == "google_business" and confidence is not None:
            lead.google_business_confidence = max(
                lead.google_business_confidence,
                confidence,
            )

        confidence_text = (
            f" confidence={confidence:.3f} ({confidence_label(confidence)})"
            if confidence is not None
            else ""
        )
        logger.info(
            "Lead enrichment found %s for %s: %s via %s%s",
            contact_type,
            lead.business_name,
            value,
            source_text,
            confidence_text,
        )
        lead.source_notes = merge_unique(
            lead.source_notes,
            [
                f"{contact_type} found via {source_text}{confidence_text}: {value}"
            ],
        )


class ContactEnrichmentService:
    def __init__(
        self,
        scraper: WebsiteScraper,
        settings: Settings,
        evidence: ContactEvidenceRecorder,
    ) -> None:
        self.scraper = scraper
        self.settings = settings
        self.evidence = evidence
        self.discovery = ContactDiscovery(
            timeout_seconds=min(settings.fetch_timeout_seconds, 8),
            max_results=settings.contact_discovery_results,
        )

    def enrich(
        self,
        lead: PlaceLead,
        payload: GenerateLeadRequest,
    ) -> ContactEnrichmentResult:
        self.evidence.record_initial(lead)
        crawl = _empty_crawl_result()
        social_from_url = _social_candidates_from_url(lead.website)
        for network, links in social_from_url.items():
            for link in links:
                self.evidence.record_social_candidate(
                    lead,
                    network,
                    link,
                    "apify_website_field",
                    0.90,
                )

        if lead.website:
            supplied_website = lead.website
            lead.website = normalize_website(lead.website)
            merge_social_candidates(social_from_url, _social_candidates_from_url(lead.website))
            if not lead.website:
                logger.info(
                    "Lead enrichment continuing without website for %s; invalid website value was %s",
                    lead.business_name,
                    supplied_website,
                )
                lead.source_notes = merge_unique(
                    lead.source_notes,
                    [f"Invalid website skipped during enrichment: {supplied_website}"],
                )
            else:
                crawl = self.scraper.crawl(lead.website)
                self._apply_primary_crawl(lead, crawl, social_from_url)
        else:
            logger.info("Lead enrichment continuing without website for %s", lead.business_name)
            lead.source_notes = merge_unique(
                lead.source_notes,
                ["No website supplied; contact discovery continued"],
            )

        lead.raw_phones = merge_unique(lead.raw_phones, list(crawl.get("phones", [])))
        social_candidates = merged_social_candidates(
            lead.social_links,
            social_from_url,
            crawl.get("social_links", {}),
        )

        if self.settings.enable_contact_discovery and (
            not lead.website
            or not lead.primary_email()
            or not social_candidates
        ):
            discovery_crawl = self._discover_missing_data(lead, payload, social_candidates)
            if discovery_crawl:
                crawl = _merge_crawl_results(crawl, discovery_crawl)

        return ContactEnrichmentResult(crawl=crawl, social_candidates=social_candidates)

    def _apply_primary_crawl(
        self,
        lead: PlaceLead,
        crawl: dict[str, Any],
        social_from_url: dict[str, list[str]],
    ) -> None:
        if not crawl.get("website_valid", True) and not social_from_url:
            logger.info(
                "Lead enrichment continuing after website validation failed for %s: %s",
                lead.business_name,
                lead.website,
            )
            lead.source_notes = merge_unique(
                lead.source_notes,
                [f"Website could not be reached during enrichment: {lead.website}"],
            )
        else:
            lead.website_text = str(crawl.get("text", ""))
            lead.pages_scraped = int(crawl.get("pages_scraped", 0))
            lead.enrichment_status = "website_crawled"
        lead.raw_emails = merge_unique(lead.raw_emails, list(crawl.get("emails", [])))
        self.evidence.record_crawl(lead, crawl)

    def _discover_missing_data(
        self,
        lead: PlaceLead,
        payload: GenerateLeadRequest,
        social_candidates: dict[str, list[str]],
    ) -> dict[str, Any]:
        location = ", ".join(part for part in (lead.address, payload.country) if part)
        logger.info(
            "Starting %s contact discovery for %s using name=%r city=%r state=%r "
            "country=%r phone_present=%s maps_url_present=%s",
            "exhaustive no-website" if not lead.website else "missing-contact",
            lead.business_name,
            lead.business_name,
            lead.city,
            lead.state,
            lead.country or payload.country,
            bool(lead.primary_phone()),
            bool(lead.google_maps_url),
        )
        result = self.discovery.search_business(
            lead.business_name,
            location,
            payload.business_type,
            address=lead.address,
            city=lead.city,
            state=lead.state,
            country=lead.country or payload.country,
            phone=lead.primary_phone(),
            website=lead.website,
            google_maps_url=lead.google_maps_url,
            exhaustive=not bool(lead.website),
        )
        if not (
            result.emails
            or result.phones
            or result.social_links
            or result.website_candidates
            or result.google_business_links
        ):
            logger.info(
                "Contact discovery found no high-confidence candidates for %s",
                lead.business_name,
            )
            return {}

        lead.raw_emails = merge_unique(lead.raw_emails, result.emails)
        lead.raw_phones = merge_unique(lead.raw_phones, result.phones)
        for email, confidence in result.email_confidence.items():
            lead.record_email_confidence(email, confidence)
        for network, scores in result.social_confidence.items():
            for link, confidence in scores.items():
                lead.record_social_confidence(network, link, confidence)
        merge_social_candidates(social_candidates, result.social_links)
        self.evidence.record_discovery(lead, result)
        if result.google_business_links:
            best_google_link = result.google_business_links[0]
            best_google_confidence = result.google_business_confidence.get(
                best_google_link,
                0.0,
            )
            if (
                not lead.google_maps_url
                or best_google_confidence > lead.google_business_confidence
            ):
                lead.google_maps_url = best_google_link
                lead.google_business_confidence = best_google_confidence
        lead.source_notes = merge_unique(
            lead.source_notes,
            [f"Contact discovery checked {url}" for url in result.source_urls[:3]],
        )

        candidate_crawl = self._crawl_discovered_website(
            lead,
            result.website_candidates,
            social_candidates,
        )
        discovery_evidence = _empty_crawl_result()
        discovery_evidence.update(
            {
                "emails": result.emails,
                "phones": result.phones,
                "social_links": result.social_links,
                "email_sources": result.email_sources,
                "phone_sources": result.phone_sources,
                "social_link_sources": result.social_sources,
            }
        )
        if lead.enrichment_status == "google_only":
            lead.enrichment_status = "contact_discovered"
        logger.info(
            "Contact discovery completed for %s: selected_email=%r "
            "social_candidates=%s google_business=%r discovered_website=%r",
            lead.business_name,
            lead.primary_email(),
            {
                network: len(links)
                for network, links in social_candidates.items()
            },
            lead.google_maps_url,
            lead.website,
        )
        return _merge_crawl_results(discovery_evidence, candidate_crawl)

    def _crawl_discovered_website(
        self,
        lead: PlaceLead,
        candidates: list[str],
        social_candidates: dict[str, list[str]],
    ) -> dict[str, Any]:
        for candidate in candidates[:2]:
            if lead.website and candidate == lead.website:
                continue
            crawl = self.scraper.crawl(candidate)
            if not crawl.get("website_valid", True):
                continue
            lead.raw_emails = merge_unique(lead.raw_emails, list(crawl.get("emails", [])))
            lead.raw_phones = merge_unique(lead.raw_phones, list(crawl.get("phones", [])))
            merge_social_candidates(social_candidates, crawl.get("social_links", {}))
            if not lead.website:
                lead.website = candidate
            self.evidence.record_crawl(lead, crawl)
            if not lead.website_text:
                lead.website_text = str(crawl.get("text", ""))
            lead.pages_scraped += int(crawl.get("pages_scraped", 0))
            return crawl
        return {}


class SocialEnrichmentService:
    def __init__(self, evidence: ContactEvidenceRecorder) -> None:
        self.evidence = evidence

    def enrich(
        self,
        lead: PlaceLead,
        candidates: dict[str, list[str]],
        crawl: dict[str, Any],
    ) -> None:
        for network, links in candidates.items():
            for link in links:
                if link not in lead.social_confidence.get(network, {}):
                    lead.record_social_confidence(network, link, 0.90)
        lead.social_links = select_social_links(
            candidates,
            confidence=lead.social_confidence,
            min_confidence=HIGH_CONFIDENCE_THRESHOLD,
        )
        lead.social_status = "found" if lead.social_links else "missing"
        for network, links in candidates.items():
            selected = lead.social_links.get(network)
            for link in links:
                confidence = lead.social_confidence.get(network, {}).get(link, 0.0)
                logger.info(
                    "Social enrichment %s candidate for %s: %s score=%.3f selected=%s",
                    network,
                    lead.business_name,
                    link,
                    confidence,
                    link == selected,
                )
        self.evidence.record_verified_social(lead, crawl)


def _social_candidates_from_url(url: str) -> dict[str, list[str]]:
    network = social_network_for_url(url)
    return {network: [url]} if network else {}


def _website_email_confidence(email: str, website: str) -> float:
    try:
        website_host = urlsplit(website).netloc.lower().removeprefix("www.")
    except ValueError:
        website_host = ""
    email_domain = email.rsplit("@", 1)[-1].lower()
    if website_host and (
        email_domain == website_host
        or email_domain.endswith(f".{website_host}")
        or website_host.endswith(f".{email_domain}")
    ):
        return 0.99
    return 0.90


def _empty_crawl_result() -> dict[str, Any]:
    return {
        "text": "",
        "emails": [],
        "phones": [],
        "social_links": {},
        "social_pages": [],
        "pages_scraped": 0,
    }


def _merge_crawl_results(primary: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    merged["text"] = "\n\n".join(
        filter(None, [str(primary.get("text", "")), str(extra.get("text", ""))])
    )[:40_000]
    merged["emails"] = merge_unique(
        list(primary.get("emails", [])),
        list(extra.get("emails", [])),
    )
    merged["phones"] = merge_unique(
        list(primary.get("phones", [])),
        list(extra.get("phones", [])),
    )
    merged["pages_scraped"] = int(primary.get("pages_scraped", 0)) + int(
        extra.get("pages_scraped", 0)
    )
    merged["social_pages"] = merge_unique(
        list(primary.get("social_pages", [])),
        list(extra.get("social_pages", [])),
    )
    merged["social_links"] = merged_social_candidates(
        primary.get("social_links", {}),
        extra.get("social_links", {}),
    )
    merged["email_sources"] = merged_source_maps(
        primary.get("email_sources", {}),
        extra.get("email_sources", {}),
    )
    merged["phone_sources"] = merged_source_maps(
        primary.get("phone_sources", {}),
        extra.get("phone_sources", {}),
    )
    merged["social_link_sources"] = merged_social_source_maps(
        primary.get("social_link_sources", {}),
        extra.get("social_link_sources", {}),
    )
    merged["website_valid"] = bool(
        primary.get("website_valid", True) or extra.get("website_valid", True)
    )
    return merged
