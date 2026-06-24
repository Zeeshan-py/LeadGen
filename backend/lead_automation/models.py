from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse
from .validation import normalize_email, normalize_phone, normalize_website


@dataclass
class PlaceLead:
    place_id: str = ""
    business_name: str = ""
    website: str = ""
    google_maps_url: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    phone: str = ""
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    lead_segment: str = "unknown"
    owner_or_contact: str = ""
    email: str = ""
    social_media: str = ""
    coverage_market: str = ""
    search_query: str = ""
    pages_scraped: int = 0
    enrichment_status: str = "google_only"
    website_text: str = ""
    raw_emails: list[str] = field(default_factory=list)
    raw_phones: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    social_status: str = "missing"
    source_notes: list[str] = field(default_factory=list)

    def primary_email(self) -> str:
        for value in [self.email, *self.raw_emails]:
            normalized = normalize_email(value)
            if normalized:
                return normalized
        return ""

    def primary_phone(self) -> str:
        for value in [self.phone, *self.raw_phones]:
            normalized = normalize_phone(value)
            if normalized:
                return normalized
        return ""

    def website_domain(self) -> str:
        website = normalize_website(self.website)
        if not website:
            return ""
        try:
            return urlparse(website).netloc.lower().removeprefix("www.")
        except Exception:
            return ""

    def dedupe_key(self) -> str:
        if self.place_id:
            return f"pid:{self.place_id}"
        domain = self.website_domain()
        if domain:
            return f"domain:{domain}"
        name_part = re.sub(r"[^a-z0-9]", "", self.business_name.lower())
        phone_part = re.sub(r"[^0-9]", "", self.primary_phone())
        return f"name:{name_part}:{phone_part}"

    def merge_extracted(self, extracted: ExtractedLead) -> None:
        if extracted.owner_or_contact and not self.owner_or_contact:
            self.owner_or_contact = extracted.owner_or_contact
        if extracted.email and not self.primary_email():
            self.email = extracted.email
            self.raw_emails = merge_unique(self.raw_emails, [extracted.email])
        if extracted.phone and not self.primary_phone():
            self.phone = extracted.phone
        if extracted.lead_segment and extracted.lead_segment != "unknown":
            self.lead_segment = extracted.lead_segment
        if extracted.source_notes:
            self.source_notes = merge_unique(self.source_notes, extracted.source_notes)


@dataclass
class ExtractedLead:
    owner_or_contact: str = ""
    email: str = ""
    phone: str = ""
    lead_segment: str = "unknown"
    source_notes: list[str] = field(default_factory=list)


def merge_unique(existing: list[str], new: list[str]) -> list[str]:
    seen = set(existing)
    result = list(existing)
    for item in new:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
