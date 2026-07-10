"""Fact extraction helpers for AI SDR conversations.

The extractor is intentionally conservative. It stores exact values where the
customer gives them clearly, and marks values as unverified when speech text is
likely uncertain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_RE = re.compile(r"\b(?:https?://)?(?:www\.)?[A-Z0-9.-]+\.[A-Z]{2,}(?:/[^\s]*)?\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+\d[\d\s().-]{7,}\d|\b\d[\d\s().-]{8,}\d\b)")


@dataclass
class ExtractedFacts:
    customer_name: str = ""
    business_name: str = ""
    website_status: str = ""
    pain_points: list[str] = field(default_factory=list)
    budget: str = ""
    timeline: str = ""
    objections: list[str] = field(default_factory=list)
    phone_numbers: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    websites: list[str] = field(default_factory=list)
    callback_requests: list[str] = field(default_factory=list)
    meeting_requests: list[str] = field(default_factory=list)
    answered_questions: list[str] = field(default_factory=list)
    unverified: dict[str, str] = field(default_factory=dict)

    def merge(self, other: "ExtractedFacts") -> None:
        self.customer_name = self.customer_name or other.customer_name
        self.business_name = self.business_name or other.business_name
        self.website_status = other.website_status or self.website_status
        self.budget = other.budget or self.budget
        self.timeline = other.timeline or self.timeline
        for field_name in (
            "pain_points",
            "objections",
            "phone_numbers",
            "emails",
            "addresses",
            "websites",
            "callback_requests",
            "meeting_requests",
            "answered_questions",
        ):
            target = getattr(self, field_name)
            for item in getattr(other, field_name):
                if item and item not in target:
                    target.append(item)
        self.unverified.update({key: value for key, value in other.unverified.items() if value})

    def to_dict(self) -> dict[str, object]:
        return {
            "customer_name": self.customer_name,
            "business_name": self.business_name,
            "website_status": self.website_status,
            "pain_points": self.pain_points,
            "budget": self.budget,
            "timeline": self.timeline,
            "objections": self.objections,
            "phone_numbers": self.phone_numbers,
            "emails": self.emails,
            "addresses": self.addresses,
            "websites": self.websites,
            "callback_requests": self.callback_requests,
            "meeting_requests": self.meeting_requests,
            "answered_questions": self.answered_questions,
            "unverified": self.unverified,
        }


class SalesMemoryExtractor:
    """Extract compact sales memory from customer speech."""

    def extract(self, message: str) -> ExtractedFacts:
        text = message.strip()
        lowered = text.lower()
        facts = ExtractedFacts()

        for email in EMAIL_RE.findall(text):
            facts.emails.append(email.lower())
        for phone in PHONE_RE.findall(text):
            normalized = normalize_phone(phone)
            if len(normalized.lstrip("+")) >= 8:
                facts.phone_numbers.append(normalized)
        for match in URL_RE.finditer(text):
            if match.start() > 0 and text[match.start() - 1] == "@":
                continue
            url = match.group(0)
            if not url.lower().startswith(("gmail.", "hotmail.", "outlook.")):
                website = normalize_website(url)
                if website not in facts.websites:
                    facts.websites.append(website)

        name = self._extract_name(text)
        if name:
            facts.customer_name = name
        business_name = self._extract_business(text)
        if business_name:
            facts.business_name = business_name

        if any(token in lowered for token in ("no website", "don't have a website", "do not have a website")):
            facts.website_status = "no website"
        elif "website" in lowered and any(token in lowered for token in ("have", "already", "existing", "got")):
            facts.website_status = "has website"

        for keyword, label in (
            ("not enough enquiries", "not enough enquiries"),
            ("no enquiries", "not enough enquiries"),
            ("not enough inquiries", "not enough enquiries"),
            ("no inquiries", "not enough enquiries"),
            ("lead", "lead flow"),
            ("inquir", "enquiry flow"),
            ("enquir", "enquiry flow"),
            ("booking", "booking friction"),
            ("reservation", "booking friction"),
            ("appointment", "appointment friction"),
            ("referral", "depends on referrals"),
            ("instagram", "depends on Instagram"),
            ("slow", "slow follow-up"),
            ("manual", "manual follow-up"),
            ("expensive", "price sensitivity"),
            ("budget", "budget concern"),
        ):
            if keyword in lowered and label not in facts.pain_points:
                facts.pain_points.append(label)

        if any(token in lowered for token in ("too expensive", "cost", "price", "budget")):
            facts.objections.append("pricing concern")
        if any(token in lowered for token in ("not interested", "don't need", "do not need")):
            facts.objections.append("not interested")
        if any(token in lowered for token in ("busy", "bad time", "call me back", "later")):
            facts.objections.append("bad timing")
            facts.callback_requests.append(text)
        if any(token in lowered for token in ("tomorrow", "next week", "monday", "tuesday", "wednesday", "thursday", "friday")):
            facts.timeline = text
        if any(token in lowered for token in ("meeting", "demo", "appointment", "book", "schedule")):
            facts.meeting_requests.append(text)
        if "budget" in lowered:
            facts.budget = text
        if any(token in lowered for token in ("address is", "located at", "we are at", "office is")):
            facts.addresses.append(text)

        if any(token in lowered for token in ("maybe", "i think", "not sure", "probably")):
            facts.unverified["latest_uncertain_value"] = text

        facts.answered_questions.append(classify_answer(text))
        return facts

    @staticmethod
    def _extract_name(text: str) -> str:
        match = re.search(
            r"\b(?:my name is|this is|i am|i'm)\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2})",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_business(text: str) -> str:
        match = re.search(
            r"\b(?:business is|company is|we are|we're)\s+([A-Z][A-Za-z0-9&.' -]{2,60})",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip(" .") if match else ""


def normalize_phone(value: str) -> str:
    prefix = "+" if value.strip().startswith("+") else ""
    digits = re.sub(r"\D", "", value)
    return f"{prefix}{digits}"


def normalize_website(value: str) -> str:
    cleaned = value.strip().rstrip(".,)")
    return cleaned if cleaned.startswith(("http://", "https://")) else f"https://{cleaned}"


def classify_answer(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("yes", "sure", "okay", "ok", "go ahead")):
        return "permission"
    if any(token in lowered for token in ("website", "instagram", "reservation", "referral", "lead", "enquir", "inquir")):
        return "discovery"
    if any(token in lowered for token in ("budget", "price", "cost")):
        return "budget"
    if any(token in lowered for token in ("tomorrow", "next week", "later", "monday", "tuesday")):
        return "timeline"
    return "general"
