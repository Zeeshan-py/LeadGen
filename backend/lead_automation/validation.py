from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$", re.I)
PHONE_RE = re.compile(r"\d")
BLOCKED_EMAIL_PREFIXES = ("noreply@", "no-reply@", "example@", "test@")


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
    return urlunsplit((parsed.scheme, host, parsed.path or "/", parsed.query, ""))


def normalize_email(value: str) -> str:
    candidate = value.strip().lower().strip("<>()[]{}.,;:")
    if (
        not candidate
        or len(candidate) > 254
        or candidate.startswith(BLOCKED_EMAIL_PREFIXES)
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
