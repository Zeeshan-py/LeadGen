from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from google import genai
from google.genai import types

from lead_automation.models import PlaceLead
from lead_automation.social_links import SOCIAL_NETWORKS, social_network_for_url


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

    def normalize_social_links(self, candidates: dict[str, list[str]]) -> dict[str, str]:
        cleaned = {
            network: list(dict.fromkeys(str(link).strip() for link in links if str(link).strip()))
            for network, links in candidates.items()
            if network in SOCIAL_NETWORKS
        }
        if not cleaned:
            return {}

        prompt = f"""
You validate and normalize social profile URLs for one local business.
Return strict JSON only. The only allowed keys are:
facebook, instagram, linkedin, youtube, x_twitter, tiktok

For each key, return one normalized https URL from the supplied candidates, or an empty string.
Rules:
- Do not invent a URL, handle, domain, or profile.
- Keep only real business profile/channel URLs. Reject share, intent, login, privacy, or generic platform URLs.
- Use only the supplied candidates for the matching network.
- Omit unsupported keys.

Candidates:
{json.dumps(cleaned, ensure_ascii=True)}
"""
        data = self._json(prompt)
        normalized: dict[str, str] = {}
        for network in SOCIAL_NETWORKS:
            value = data.get(network)
            if not isinstance(value, str) or not value.strip():
                continue
            link = value.strip()
            if social_network_for_url(link) != network:
                continue
            if any(_same_social_destination(link, candidate) for candidate in cleaned.get(network, [])):
                normalized[network] = link
        return normalized

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


def _same_social_destination(left: str, right: str) -> bool:
    try:
        left_parts = urlsplit(left)
        right_parts = urlsplit(right)
    except ValueError:
        return False
    left_key = (left_parts.netloc.lower().removeprefix("www."), left_parts.path.rstrip("/").lower())
    right_key = (right_parts.netloc.lower().removeprefix("www."), right_parts.path.rstrip("/").lower())
    return left_key == right_key
