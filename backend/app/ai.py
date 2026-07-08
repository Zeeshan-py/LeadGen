"""AI analysis and outreach generation adapter.

This module wraps Gemini interactions and converts website/lead context into
structured analysis and sales copy used by the CRM and outreach workflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from lead_automation.models import PlaceLead


@dataclass(frozen=True)
class WebsiteAnalysis:
    website_score: int
    opportunity_score: int
    website_problems: list[str]
    website_summary: str
    improvement_suggestions: list[str]


@dataclass(frozen=True)
class OutreachDrafts:
    subject_line: str
    personalized_first_line: str
    cold_email: str
    follow_up_1: str
    follow_up_2: str
    generation_error: str = ""


class GeminiLeadAI:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for website analysis and outreach generation.")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def analyze_website(self, lead: PlaceLead, business_type: str, crawl: dict[str, Any]) -> WebsiteAnalysis:
        text = str(crawl.get("text", ""))[:12000]
        prompt = f"""
You are LeadForge AI, an internal lead qualification analyst.

Analyze this local business website for a web design / marketing opportunity.
Return strict JSON only with these keys:
website_score: integer 0-100 where 100 means excellent website
opportunity_score: integer 0-100 where 100 means strong chance they need help
website_problems: array of concise strings
website_summary: one concise paragraph
improvement_suggestions: array of concise, specific recommendations

Scoring factors:
- Website design quality
- SEO issues
- Mobile responsiveness signals
- Speed and technical problems
- Missing contact forms
- Missing SSL or trust signals
- Old design / weak conversion path

Business:
Name: {lead.business_name}
Type: {business_type}
Website: {lead.website}
Location: {lead.address}
Google phone: {lead.phone}
Emails found: {", ".join(lead.raw_emails) or "none"}
Phones found on website: {", ".join(lead.raw_phones) or "none"}

Website text:
{text or "No readable website text was available."}
"""
        data = self._json(prompt)
        return WebsiteAnalysis(
            website_score=_clamp_int(data.get("website_score"), default=50),
            opportunity_score=_clamp_int(data.get("opportunity_score"), default=50),
            website_problems=_string_list(data.get("website_problems")),
            website_summary=str(data.get("website_summary", "")).strip(),
            improvement_suggestions=_string_list(data.get("improvement_suggestions")),
        )

    def generate_outreach(
        self,
        lead: PlaceLead,
        business_type: str,
        analysis: WebsiteAnalysis,
    ) -> OutreachDrafts:
        prompt = f"""
You are LeadForge AI writing concise, respectful cold outreach for one internal operator.
Return strict JSON only with:
subject_line
personalized_first_line
cold_email
follow_up_1
follow_up_2

Rules:
- Do not fabricate awards, customers, personal names, or facts not supplied.
- Mention one specific website opportunity from the analysis.
- Keep emails practical, human, and under 130 words each.
- The offer is website/design/SEO improvement help.

Lead:
Business name: {lead.business_name}
Business type: {business_type}
Website: {lead.website}
Location: {lead.address}
Email: {lead.primary_email() or "unknown"}
Phone: {lead.primary_phone() or "unknown"}

Website analysis:
Score: {analysis.website_score}
Opportunity score: {analysis.opportunity_score}
Summary: {analysis.website_summary}
Problems: {"; ".join(analysis.website_problems)}
Suggestions: {"; ".join(analysis.improvement_suggestions)}
"""
        data = self._json(prompt)
        return OutreachDrafts(
            subject_line=str(data.get("subject_line", "")).strip(),
            personalized_first_line=str(data.get("personalized_first_line", "")).strip(),
            cold_email=str(data.get("cold_email", "")).strip(),
            follow_up_1=str(data.get("follow_up_1", "")).strip(),
            follow_up_2=str(data.get("follow_up_2", "")).strip(),
        )

    def _json(self, prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        text = (response.text or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise


def fallback_outreach_drafts(
    lead: PlaceLead,
    business_type: str,
    analysis: WebsiteAnalysis,
    generation_error: str = "",
) -> OutreachDrafts:
    business_name = lead.business_name.strip() or "your business"
    location = lead.city.strip() or lead.address.strip()
    location_suffix = f" in {location}" if location else ""
    first_line = (
        f"I came across {business_name}{location_suffix} and wanted to reach out "
        "with a practical idea."
    )
    if lead.website:
        problem = analysis.website_problems[0] if analysis.website_problems else ""
        opportunity = (
            f"One opportunity I noticed is {problem.rstrip('.').lower()}."
            if problem
            else "There may be room to make the website clearer and easier for potential customers to use."
        )
    else:
        opportunity = (
            "I could not find a dedicated website, which may make it harder for "
            "potential customers to discover your services and get in touch."
        )
    niche = business_type.strip().lower() or "local"
    cold_email = (
        f"Hi,\n\n{first_line}\n\n{opportunity} I help {niche} businesses improve "
        "their website, local visibility, and conversion path without making the "
        "process complicated.\n\nWould you be open to a brief conversation about "
        f"a few ideas for {business_name}?\n\nBest,"
    )
    return OutreachDrafts(
        subject_line=f"A website idea for {business_name}",
        personalized_first_line=first_line,
        cold_email=cold_email,
        follow_up_1=(
            f"Hi,\n\nJust following up on the website idea I sent for {business_name}. "
            "I would be happy to share a few concise recommendations if improving "
            "online visibility is a priority.\n\nBest,"
        ),
        follow_up_2=(
            f"Hi,\n\nI will close the loop after this note. If you would ever like "
            f"a straightforward website or local SEO review for {business_name}, "
            "I would be glad to help.\n\nBest,"
        ),
        generation_error=generation_error,
    )


def _clamp_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(100, parsed))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
