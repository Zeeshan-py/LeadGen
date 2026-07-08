"""Contact normalization for AI SDR source records.

Source adapters can submit loose dictionaries; this module converts them into
canonical CRM-ready contact data with dedupe keys, normalized URLs, tags, and
validation errors.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai_sdr.schemas import AISDRContactInput, AISDRSourceType


SOURCE_TAGS = {
    AISDRSourceType.CSV: "CSV",
    AISDRSourceType.EXCEL: "Excel",
    AISDRSourceType.GOOGLE_SHEETS: "Google Sheets",
    AISDRSourceType.MANUAL_ENTRY: "Manual Entry",
    AISDRSourceType.REST_API: "REST API",
    AISDRSourceType.CRM: "CRM",
    AISDRSourceType.FUTURE_INTEGRATION: "Future Integration",
}


@dataclass(frozen=True)
class NormalizedContact:
    source_type: str
    external_id: str
    business_name: str
    contact_name: str
    title: str
    email: str
    phone: str
    website: str
    linkedin_url: str
    address: str
    city: str
    state: str
    country: str
    industry: str
    notes: str
    tags: list[str]
    dedupe_key: str
    raw: dict[str, Any]
    errors: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "external_id": self.external_id,
            "business_name": self.business_name,
            "contact_name": self.contact_name,
            "title": self.title,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "linkedin_url": self.linkedin_url,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "industry": self.industry,
            "notes": self.notes,
            "tags": self.tags,
            "dedupe_key": self.dedupe_key,
        }


def normalize_contact(contact: AISDRContactInput, source_type: AISDRSourceType) -> NormalizedContact:
    raw_payload = contact_to_raw_payload(contact)
    combined = _combined_mapping(raw_payload)
    first_name = _clean_text(_pick(combined, "first_name", "firstName", "given_name", "givenName"))
    last_name = _clean_text(_pick(combined, "last_name", "lastName", "family_name", "familyName"))
    contact_name = _clean_text(
        _pick(combined, "contact_name", "contactName", "full_name", "fullName", "name")
    )
    if not contact_name:
        contact_name = " ".join(part for part in [first_name, last_name] if part)

    business_name = _clean_text(
        _pick(
            combined,
            "business_name",
            "businessName",
            "company_name",
            "companyName",
            "company",
            "account_name",
            "accountName",
            "organization",
        )
    )
    email = _normalize_email(_pick(combined, "email", "email_address", "emailAddress", "work_email"))
    phone = _normalize_phone(_pick(combined, "phone", "phone_number", "phoneNumber", "mobile", "telephone"))
    website = _normalize_website(_pick(combined, "website", "url", "company_url", "companyUrl", "domain"))
    linkedin_url = _normalize_website(_pick(combined, "linkedin_url", "linkedinUrl", "linkedin"))
    address = _clean_text(_pick(combined, "address", "street_address", "streetAddress", "location"))
    city = _clean_text(_pick(combined, "city", "locality"))
    state = _clean_text(_pick(combined, "state", "region", "province"))
    country = _clean_text(_pick(combined, "country", "country_name", "countryName"))
    industry = _clean_text(_pick(combined, "industry", "business_type", "businessType", "vertical"))
    title = _clean_text(_pick(combined, "title", "job_title", "jobTitle", "role"))
    notes = _clean_text(_pick(combined, "notes", "note", "description"))
    external_id = _clean_text(_pick(combined, "external_id", "externalId", "id", "source_id", "sourceId"))
    tags = _normalize_tags(_pick(combined, "tags", "tag"), source_type)

    errors: list[str] = []
    if not any([business_name, contact_name, email, phone, website]):
        errors.append("Contact must include company, contact, email, phone, or website.")
    if not business_name:
        business_name = contact_name or email or phone or "Unknown Company"

    dedupe_key = _dedupe_key(email=email, website=website, phone=phone, business_name=business_name, country=country)
    return NormalizedContact(
        source_type=source_type.value,
        external_id=external_id,
        business_name=business_name,
        contact_name=contact_name,
        title=title,
        email=email,
        phone=phone,
        website=website,
        linkedin_url=linkedin_url,
        address=address,
        city=city,
        state=state,
        country=country,
        industry=industry,
        notes=notes,
        tags=tags,
        dedupe_key=dedupe_key,
        raw=raw_payload,
        errors=errors,
    )


def contact_to_raw_payload(contact: AISDRContactInput) -> dict[str, Any]:
    payload = contact.model_dump(exclude_none=True)
    if contact.model_extra:
        payload.update(contact.model_extra)
    return payload


def domain_from_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    return host.removeprefix("www.")


def _combined_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("raw")
    if isinstance(raw, dict):
        return {**raw, **payload}
    return dict(payload)


def _pick(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    return " ".join(str(value).strip().split())


def _normalize_email(value: Any) -> str:
    email = _clean_text(value).lower()
    return email if "@" in email and "." in email.rsplit("@", 1)[-1] else ""


def _normalize_phone(value: Any) -> str:
    phone = _clean_text(value)
    phone = re.sub(r"[\s().-]+", " ", phone).strip()
    return phone[:80]


def _normalize_website(value: Any) -> str:
    website = _clean_text(value)
    if not website:
        return ""
    if "@" in website and "://" not in website:
        return ""
    if "://" not in website:
        website = f"https://{website}"
    parsed = urlsplit(website)
    if not parsed.netloc:
        return ""
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))


def _normalize_tags(value: Any, source_type: AISDRSourceType) -> list[str]:
    raw_tags: list[str]
    if isinstance(value, str):
        raw_tags = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_tags = [str(part).strip() for part in value]
    else:
        raw_tags = []
    tags = ["AI SDR", SOURCE_TAGS[source_type], *raw_tags]
    return list(dict.fromkeys(tag[:80] for tag in tags if tag))


def _dedupe_key(*, email: str, website: str, phone: str, business_name: str, country: str) -> str:
    if email:
        return f"email:{email}"
    domain = domain_from_url(website)
    if domain:
        return f"domain:{domain}"
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 7:
        return f"phone:{digits[-15:]}"
    basis = "|".join([business_name.lower(), country.lower()]).strip("|") or "unknown"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"ai_sdr:{digest}"
