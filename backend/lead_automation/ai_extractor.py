from __future__ import annotations

import json

import anthropic

from .models import ExtractedLead, PlaceLead

MODEL = "claude-haiku-4-5"

EXTRACT_TOOL = {
    "name": "extract_lead",
    "description": "Extract structured contact information from a landscaping business website.",
    "input_schema": {
        "type": "object",
        "properties": {
            "owner_or_contact": {
                "type": "string",
                "description": "Primary contact or owner name. Leave blank if not found or uncertain.",
            },
            "email": {
                "type": "string",
                "description": "Best contact email address. Leave blank if not found.",
            },
            "phone": {
                "type": "string",
                "description": "Best contact phone number. Leave blank if not found.",
            },
            "lead_segment": {
                "type": "string",
                "enum": [
                    "design_build",
                    "commercial_contractor",
                    "high_end_residential",
                    "landscape_architecture",
                    "green_roof",
                    "materials_distributor",
                    "unknown",
                ],
                "description": "Best classification based on the business description.",
            },
            "source_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short notes on where contact info was found (e.g. 'email from contact page').",
            },
        },
        "required": ["owner_or_contact", "email", "phone", "lead_segment", "source_notes"],
    },
}

SYSTEM_PROMPT = (
    "You extract contact information from landscaping business websites. "
    "You are helping a moss supplier identify decision-makers at landscaping firms. "
    "Target business types: design-build contractors, commercial landscape contractors, "
    "high-end residential landscapers, landscape architects, green roof contractors. "
    "If the business is clearly a lawn care, mowing, tree service, or handyman operation with no "
    "design/installation signals, set lead_segment to 'unknown'. "
    "Only extract what is clearly present — never guess or fabricate contact details."
)


def _build_prompt(lead: PlaceLead) -> str:
    parts = [
        f"Business: {lead.business_name}",
        f"Address: {lead.address}",
        f"Website: {lead.website}",
        f"Phone from Google Maps: {lead.phone}",
        f"Emails found on site: {', '.join(lead.raw_emails) or 'none'}",
        f"Phones found on site: {', '.join(lead.raw_phones) or 'none'}",
    ]
    if lead.website_text:
        snippet = _relevant_snippet(lead.website_text)
        parts.append(f"\nWebsite text (excerpt):\n{snippet}")
    return "\n".join(parts)


def _relevant_snippet(text: str, max_chars: int = 5000) -> str:
    priority_words = (
        "contact", "email", "phone", "owner", "director", "president",
        "design", "install", "construction", "commercial", "luxury", "architect",
    )
    lines = text.split("\n")
    scored: list[tuple[int, str]] = []
    for line in lines:
        lower = line.lower()
        score = sum(1 for w in priority_words if w in lower)
        scored.append((score, line))
    scored.sort(key=lambda x: -x[0])
    result = "\n".join(line for _, line in scored[:200])
    return result[:max_chars]


class LeadExtractor:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract(self, lead: PlaceLead) -> ExtractedLead:
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_lead"},
                messages=[{"role": "user", "content": _build_prompt(lead)}],
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "extract_lead":
                    inp = block.input
                    return ExtractedLead(
                        owner_or_contact=inp.get("owner_or_contact", ""),
                        email=inp.get("email", ""),
                        phone=inp.get("phone", ""),
                        lead_segment=inp.get("lead_segment", "unknown"),
                        source_notes=inp.get("source_notes", []),
                    )
        except Exception as exc:
            pass
        return ExtractedLead()
