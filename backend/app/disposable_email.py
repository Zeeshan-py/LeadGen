"""Disposable email protection for account signup."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from .auth import normalize_email
from .config import Settings

DISPOSABLE_EMAIL_REJECTION = "Disposable email addresses are not allowed."

logger = logging.getLogger("leadforge.disposable_email")

_domains_lock = threading.RLock()
_disposable_domains: set[str] = set()
_last_domain_refresh_at: datetime | None = None

_abstract_cache_lock = threading.RLock()
_abstract_cache: dict[str, "AbstractEmailCacheEntry"] = {}


@dataclass(frozen=True)
class AbstractEmailCacheEntry:
    is_disposable: bool
    expires_at: datetime


class DisposableEmailRejected(ValueError):
    """Raised when signup attempts to use a disposable email address."""


def load_disposable_email_domains(settings: Settings) -> None:
    """Load cached domains first, then refresh the in-memory set from GitHub."""

    _load_domains_from_cache_file(settings.disposable_email_cache_path)
    refresh_disposable_email_domains(settings)


def refresh_disposable_email_domains(settings: Settings) -> None:
    """Download the latest blocklist, preserving the existing set on failure."""

    try:
        with httpx.Client(timeout=settings.disposable_email_fetch_timeout_seconds, follow_redirects=True) as client:
            response = client.get(settings.disposable_email_blocklist_url)
            response.raise_for_status()
        domains = _parse_domain_list(response.text)
        if not domains:
            raise ValueError("downloaded disposable email blocklist was empty")
        _replace_disposable_domains(domains)
        _save_domains_to_cache_file(settings.disposable_email_cache_path, domains)
        logger.info("Loaded %s disposable email domains", len(domains))
    except Exception:
        logger.exception(
            "Unable to refresh disposable email domains; keeping %s in-memory domains",
            disposable_domain_count(),
        )


def ensure_signup_email_allowed(email: str, settings: Settings) -> None:
    clean_email = normalize_email(email)
    domain = email_domain(clean_email)
    if domain and is_disposable_domain(domain):
        raise DisposableEmailRejected(DISPOSABLE_EMAIL_REJECTION)

    if is_disposable_by_abstract(clean_email, settings):
        raise DisposableEmailRejected(DISPOSABLE_EMAIL_REJECTION)


def is_disposable_domain(domain: str) -> bool:
    normalized = normalize_domain(domain)
    if not normalized:
        return False
    with _domains_lock:
        domains = _disposable_domains.copy()
    for candidate in domain_candidates(normalized):
        if candidate in domains:
            return True
    return False


def is_disposable_by_abstract(email: str, settings: Settings) -> bool:
    if not settings.abstract_email_api_key:
        return False

    clean_email = normalize_email(email)
    cached = _abstract_cache_get(clean_email)
    if cached is not None:
        return cached

    try:
        with httpx.Client(timeout=settings.abstract_email_timeout_seconds) as client:
            response = client.get(
                settings.abstract_email_reputation_url,
                params={"email": clean_email},
                headers={"Authorization": f"Bearer {settings.abstract_email_api_key}"},
            )
            response.raise_for_status()
        is_disposable = _abstract_payload_is_disposable(response.json())
        _abstract_cache_set(clean_email, is_disposable, ttl_hours=settings.abstract_email_cache_hours)
        return is_disposable
    except Exception:
        logger.exception("Abstract Email Reputation API check failed; allowing signup for %s", _redact_email(clean_email))
        return False


def email_domain(email: str) -> str:
    clean_email = normalize_email(email)
    if "@" not in clean_email:
        return ""
    return normalize_domain(clean_email.rsplit("@", 1)[1])


def normalize_domain(domain: str) -> str:
    value = domain.strip().strip(".").lower()
    if not value:
        return ""
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError:
        return value


def domain_candidates(domain: str) -> list[str]:
    labels = [part for part in normalize_domain(domain).split(".") if part]
    candidates: list[str] = []
    for index in range(max(len(labels) - 1, 0)):
        candidates.append(".".join(labels[index:]))
    return candidates


def disposable_domain_count() -> int:
    with _domains_lock:
        return len(_disposable_domains)


def clear_abstract_email_cache() -> None:
    with _abstract_cache_lock:
        _abstract_cache.clear()


def replace_disposable_domains_for_tests(domains: Iterable[str]) -> None:
    _replace_disposable_domains(set(domains))


def _replace_disposable_domains(domains: Iterable[str]) -> None:
    parsed = {normalize_domain(domain) for domain in domains}
    parsed = {domain for domain in parsed if domain and "." in domain}
    with _domains_lock:
        _disposable_domains.clear()
        _disposable_domains.update(parsed)
        global _last_domain_refresh_at
        _last_domain_refresh_at = _utc_now()


def _parse_domain_list(text: str) -> set[str]:
    domains: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        domain = normalize_domain(line.lstrip("@"))
        if domain and "." in domain:
            domains.add(domain)
    return domains


def _load_domains_from_cache_file(path: Path) -> None:
    try:
        if not path.exists():
            return
        domains = _parse_domain_list(path.read_text(encoding="utf-8"))
        if domains:
            _replace_disposable_domains(domains)
            logger.info("Loaded %s disposable email domains from local cache", len(domains))
    except Exception:
        logger.exception("Unable to load disposable email domain cache from %s", path)


def _save_domains_to_cache_file(path: Path, domains: set[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(sorted(domains)) + "\n", encoding="utf-8")
    except Exception:
        logger.exception("Unable to write disposable email domain cache to %s", path)


def _abstract_cache_get(email: str) -> bool | None:
    now = _utc_now()
    with _abstract_cache_lock:
        cached = _abstract_cache.get(email)
        if not cached:
            return None
        if cached.expires_at <= now:
            _abstract_cache.pop(email, None)
            return None
        return cached.is_disposable


def _abstract_cache_set(email: str, is_disposable: bool, *, ttl_hours: int) -> None:
    with _abstract_cache_lock:
        _abstract_cache[email] = AbstractEmailCacheEntry(
            is_disposable=is_disposable,
            expires_at=_utc_now() + timedelta(hours=ttl_hours),
        )


def _abstract_payload_is_disposable(payload: dict[str, Any]) -> bool:
    quality = payload.get("email_quality") if isinstance(payload.get("email_quality"), dict) else {}
    if isinstance(quality.get("is_disposable"), bool):
        return bool(quality["is_disposable"])

    legacy = payload.get("is_disposable_email") if isinstance(payload.get("is_disposable_email"), dict) else {}
    if isinstance(legacy.get("value"), bool):
        return bool(legacy["value"])

    return False


def _redact_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local:
        return f"***@{domain}" if domain else "***"
    return f"{local[:1]}***@{domain}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
