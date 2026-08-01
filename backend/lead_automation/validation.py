"""Validation helpers for normalized lead and contact data."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from .url_safety import is_safe_public_url

if TYPE_CHECKING:
    from .models import PlaceLead

EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$", re.I)
PHONE_RE = re.compile(r"\d")
BLOCKED_EMAIL_PREFIXES = ("noreply@", "no-reply@", "example@", "test@")
BLOCKED_EMAIL_DOMAINS = {
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "example.com",
}


def normalize_website(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    host = parsed.netloc.lower().strip(".")
    if parsed.scheme not in {"http", "https"} or not host or "." not in host:
        return ""
    if host in {"localhost", "example.com"}:
        return ""
    normalized = urlunsplit((parsed.scheme, host, parsed.path or "/", parsed.query, ""))
    if not is_safe_public_url(normalized, resolve=False):
        return ""
    return normalized


def normalize_email(value: str) -> str:
    candidate = value.strip().lower().strip("<>()[]{}.,;:")
    domain = candidate.rsplit("@", 1)[-1] if "@" in candidate else ""
    if (
        not candidate
        or len(candidate) > 254
        or candidate.startswith(BLOCKED_EMAIL_PREFIXES)
        or domain in BLOCKED_EMAIL_DOMAINS
        or not EMAIL_RE.fullmatch(candidate)
    ):
        return ""
    return candidate


def normalize_phone(value: str) -> str:
    candidate = value.strip()
    digits = "".join(PHONE_RE.findall(candidate))
    if len(digits) < 7 or len(digits) > 15 or len(set(digits)) < 3:
        return ""
    prefix = "+" if candidate.startswith("+") else ""
    return f"{prefix}{digits}"


def qualifies_google_business(lead: PlaceLead) -> bool:
    if lead.user_rating_count is not None and lead.user_rating_count < 5:
        return False
    if lead.rating is not None and lead.rating < 3.0:
        return False
    return True
