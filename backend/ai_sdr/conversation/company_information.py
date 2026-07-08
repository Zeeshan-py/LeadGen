"""Company context model used by the AI SDR conversation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import Lead


@dataclass(frozen=True)
class CompanyInformation:
    """Business context that lets AI SDR responses sound specific and relevant."""

    business_name: str
    industry: str = ""
    website: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    website_summary: str = ""
    website_problems: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    previous_interactions: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_lead(cls, lead: Lead, *, previous_interactions: list[str] | None = None) -> "CompanyInformation":
        """Build conversation-ready company context from a CRM lead record."""

        return cls(
            business_name=lead.business_name or "your business",
            industry=lead.business_type or "",
            website=lead.website or "",
            city=lead.city or "",
            state=lead.state or "",
            country=lead.country or "",
            website_summary=lead.website_summary or "",
            website_problems=list(lead.website_problems or []),
            improvement_suggestions=list(lead.improvement_suggestions or []),
            previous_interactions=previous_interactions or _notes_to_interactions(lead.notes),
            raw=dict(lead.raw or {}),
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CompanyInformation":
        """Build company context from ad-hoc API payloads."""

        return cls(
            business_name=_clean(payload.get("business_name") or payload.get("company") or "your business"),
            industry=_clean(payload.get("industry")),
            website=_clean(payload.get("website")),
            city=_clean(payload.get("city")),
            state=_clean(payload.get("state")),
            country=_clean(payload.get("country")),
            website_summary=_clean(payload.get("website_summary")),
            website_problems=[str(item).strip() for item in payload.get("website_problems", []) if str(item).strip()],
            improvement_suggestions=[
                str(item).strip() for item in payload.get("improvement_suggestions", []) if str(item).strip()
            ],
            previous_interactions=[
                str(item).strip() for item in payload.get("previous_interactions", []) if str(item).strip()
            ],
            raw=dict(payload.get("raw") or {}),
        )

    @property
    def location_phrase(self) -> str:
        if self.city and self.state:
            return f"{self.city}, {self.state}"
        return self.city or self.state or self.country

    @property
    def industry_phrase(self) -> str:
        return self.industry or "your market"

    def context_line(self) -> str:
        pieces = [self.business_name]
        if self.industry:
            pieces.append(f"in {self.industry}")
        if self.location_phrase:
            pieces.append(f"around {self.location_phrase}")
        return " ".join(pieces)

    def website_reference(self) -> str:
        if self.website_summary:
            return self.website_summary
        if self.website_problems:
            return self.website_problems[0]
        if self.improvement_suggestions:
            return self.improvement_suggestions[0]
        if self.website:
            return "I noticed your website is live, so I wanted to understand whether it is already helping convert visitors into conversations."
        return "I did not see a website recorded, so I would want to confirm where most new customer inquiries come from today."

    def previous_interaction_reference(self) -> str:
        if not self.previous_interactions:
            return ""
        return self.previous_interactions[0]


def _notes_to_interactions(notes: str | None) -> list[str]:
    if not notes or not notes.strip():
        return []
    return [notes.strip()]


def _clean(value: Any) -> str:
    return str(value or "").strip()
