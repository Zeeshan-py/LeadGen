"""Owner/contact context model used by the AI SDR conversation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import Lead


@dataclass(frozen=True)
class OwnerInformation:
    """Owner or contact context used to personalize AI SDR turns."""

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""

    @classmethod
    def from_lead(cls, lead: Lead) -> "OwnerInformation":
        """Extract owner fields from a CRM lead and AI SDR raw metadata."""

        raw = dict(lead.raw or {})
        ai_sdr = dict(raw.get("ai_sdr") or {})
        return cls(
            name=lead.contact_name or "",
            title=str(ai_sdr.get("title") or "").strip(),
            email=lead.email or "",
            phone=lead.phone or "",
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "OwnerInformation":
        """Build owner context from ad-hoc API payloads."""

        return cls(
            name=str(payload.get("name") or payload.get("contact") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            email=str(payload.get("email") or "").strip(),
            phone=str(payload.get("phone") or "").strip(),
        )

    @property
    def display_name(self) -> str:
        return self.name or "there"

    @property
    def role_phrase(self) -> str:
        if self.title:
            return self.title
        return "owner"
