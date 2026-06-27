from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

HIGH_CONFIDENCE_THRESHOLD = 0.65
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LEGAL_NAME_TOKENS = {
    "and",
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "the",
}
_PUBLIC_EMAIL_HOSTS = {
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "outlook.com",
    "yahoo.com",
}


@dataclass(frozen=True)
class DiscoveryIdentity:
    business_name: str
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    phone: str = ""
    website: str = ""
    google_maps_url: str = ""


def identity_match_score(identity: DiscoveryIdentity | None, evidence: str) -> float:
    if identity is None:
        return 0.70

    evidence_text = urllib.parse.unquote(evidence).lower()
    evidence_tokens = set(_tokens(evidence_text))
    name_tokens = set(_name_tokens(identity.business_name))
    if not name_tokens:
        return 0.0

    name_ratio = len(name_tokens & evidence_tokens) / len(name_tokens)
    score = 0.20 + (0.45 * name_ratio)
    if _contains_value(evidence_text, identity.city):
        score += 0.10
    if _contains_value(evidence_text, identity.state):
        score += 0.07
    if _contains_value(evidence_text, identity.country):
        score += 0.03
    if _phone_matches(evidence_text, identity.phone):
        score += 0.15

    address_tokens = set(_tokens(identity.address)) - name_tokens
    if address_tokens:
        address_ratio = len(address_tokens & evidence_tokens) / len(address_tokens)
        score += min(0.10, address_ratio * 0.10)
    return _clamp(score)


def email_candidate_confidence(
    email: str,
    evidence: str,
    identity: DiscoveryIdentity | None,
    result_url: str = "",
) -> float:
    score = identity_match_score(identity, evidence)
    email_domain = email.rsplit("@", 1)[-1].lower()
    if email_domain and email_domain not in _PUBLIC_EMAIL_HOSTS:
        if _domain_matches_url(email_domain, result_url):
            score += 0.18
        if identity and _domain_matches_url(email_domain, identity.website):
            score += 0.20
    return _clamp(score)


def social_candidate_confidence(
    url: str,
    evidence: str,
    identity: DiscoveryIdentity | None,
) -> float:
    score = identity_match_score(identity, f"{evidence} {url}")
    if identity:
        name_tokens = set(_name_tokens(identity.business_name))
        url_tokens = set(_tokens(urllib.parse.unquote(url)))
        if name_tokens and len(name_tokens & url_tokens) / len(name_tokens) >= 0.5:
            score += 0.07
        if _phone_matches(url, identity.phone):
            score += 0.12
    return _clamp(score)


def website_candidate_confidence(
    url: str,
    evidence: str,
    identity: DiscoveryIdentity | None,
) -> float:
    score = identity_match_score(identity, f"{evidence} {url}")
    if identity:
        name_tokens = set(_name_tokens(identity.business_name))
        host_tokens = set(_tokens(urllib.parse.urlsplit(url).netloc))
        if name_tokens and len(name_tokens & host_tokens) / len(name_tokens) >= 0.5:
            score += 0.10
    return _clamp(score)


def google_business_candidate_confidence(
    url: str,
    evidence: str,
    identity: DiscoveryIdentity | None,
) -> float:
    score = identity_match_score(identity, f"{evidence} {url}")
    if identity and identity.google_maps_url and _same_url(identity.google_maps_url, url):
        score = max(score, 0.99)
    return _clamp(score + 0.05)


def is_high_confidence(score: float) -> bool:
    return score >= HIGH_CONFIDENCE_THRESHOLD


def confidence_label(score: float) -> str:
    if score >= 0.90:
        return "very_high"
    if score >= 0.75:
        return "high"
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _name_tokens(value: str) -> list[str]:
    return [token for token in _tokens(value) if token not in _LEGAL_NAME_TOKENS]


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.lower())


def _contains_value(evidence: str, value: str) -> bool:
    clean = " ".join(_tokens(value))
    return bool(clean and clean in " ".join(_tokens(evidence)))


def _phone_matches(evidence: str, phone: str) -> bool:
    expected = "".join(character for character in phone if character.isdigit())
    actual = "".join(character for character in evidence if character.isdigit())
    return bool(len(expected) >= 7 and expected[-7:] in actual)


def _domain_matches_url(domain: str, url: str) -> bool:
    if not url:
        return False
    try:
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return False
    return host == domain or host.endswith(f".{domain}") or domain.endswith(f".{host}")


def _same_url(left: str, right: str) -> bool:
    try:
        left_parts = urllib.parse.urlsplit(left)
        right_parts = urllib.parse.urlsplit(right)
    except ValueError:
        return False
    return (
        left_parts.netloc.lower().removeprefix("www."),
        left_parts.path.rstrip("/").lower(),
    ) == (
        right_parts.netloc.lower().removeprefix("www."),
        right_parts.path.rstrip("/").lower(),
    )


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
