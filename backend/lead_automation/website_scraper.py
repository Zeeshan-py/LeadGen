"""Website fetching and scraping helpers for lead enrichment."""

from __future__ import annotations

import re
import ssl
import logging
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from .social_links import (
    SocialExtraction,
    extract_social_links_with_sources,
    flatten_social_links,
    merge_social_candidates,
)
from .source_maps import add_source, merge_social_source_map, merge_source_map
from .validation import normalize_email, normalize_phone, normalize_website

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")
CF_EMAIL_RE = re.compile(r'data-cfemail="([0-9a-f]+)"')
logger = logging.getLogger(__name__)

PAGE_TARGETS = (
    ("contact", ("contact", "contact-us", "get-in-touch", "reach-us", "connect")),
    ("about", ("about", "about-us", "our-story", "who-we-are")),
)


@dataclass(frozen=True)
class ParsedPage:
    text: str
    emails: list[str]
    phones: list[str]
    social: SocialExtraction


class WebsiteScraper:
    def __init__(
        self,
        timeout_seconds: int = 20,
        max_pages: int = 5,
        js_fallback: Any = None,
    ) -> None:
        self.timeout = timeout_seconds
        self.max_pages = max_pages
        self.js_fallback = js_fallback
        self._ssl_ctx = ssl.create_default_context()

    def crawl(self, url: str) -> dict[str, Any]:
        url = normalize_website(url)
        if not url:
            return {
                "text": "", "emails": [], "phones": [], "pages_scraped": 0,
                "social_links": {}, "social_pages": [], "website_valid": False,
                "email_sources": {}, "phone_sources": {}, "social_link_sources": {},
            }
        visited: set[str] = set()
        all_text: list[str] = []
        all_emails: list[str] = []
        all_phones: list[str] = []
        email_sources: dict[str, list[str]] = {}
        phone_sources: dict[str, list[str]] = {}
        social_candidates: dict[str, list[str]] = {}
        social_sources: dict[str, dict[str, list[str]]] = {}
        social_pages: list[str] = []

        html = self._fetch(url)
        if html is None:
            fallback = self._try_js_fallback(url, reason="fetch_failed")
            fallback["website_valid"] = bool(fallback.get("text"))
            return fallback

        visited.add(url)
        homepage = self._parse_page(html, url, "homepage", email_sources, phone_sources)
        all_text.append(homepage.text)
        all_emails.extend(homepage.emails)
        all_phones.extend(homepage.phones)
        _merge_social_extraction(
            social_candidates,
            social_sources,
            homepage.social,
        )
        social_pages.extend(("homepage", "homepage_header_footer"))

        for page_name, slugs in PAGE_TARGETS:
            if len(visited) >= self.max_pages:
                break
            target = self._fetch_target_page(html, url, page_name, slugs, visited)
            if target is None:
                continue
            candidate, sub_html = target
            visited.add(candidate)
            page = self._parse_page(sub_html, candidate, page_name, email_sources, phone_sources)
            all_text.append(page.text)
            all_emails.extend(page.emails)
            all_phones.extend(page.phones)
            _merge_social_extraction(social_candidates, social_sources, page.social)
            social_pages.append(page_name)

        pages_scraped = len(visited)

        combined_text = "\n\n".join(filter(None, all_text))
        emails_unique = list(dict.fromkeys(all_emails))
        phones_unique = list(dict.fromkeys(all_phones))
        social_links = flatten_social_links(social_candidates)

        if _looks_js_rendered(combined_text, emails_unique, phones_unique):
            fb = self._try_js_fallback(url, reason="thin_content")
            if fb.get("text"):
                merge_source_map(email_sources, fb.get("email_sources", {}))
                merge_source_map(phone_sources, fb.get("phone_sources", {}))
                merge_social_source_map(social_sources, fb.get("social_link_sources", {}))
                merge_social_candidates(social_candidates, fb.get("social_links", {}))
                return {
                    "text": (combined_text + "\n\n" + str(fb.get("text", "")))[:40_000],
                    "emails": list(dict.fromkeys(emails_unique + list(fb.get("emails", [])))),
                    "phones": list(dict.fromkeys(phones_unique + list(fb.get("phones", [])))),
                    "pages_scraped": pages_scraped + int(fb.get("pages_scraped", 0)),
                    "social_links": flatten_social_links(social_candidates),
                    "social_pages": list(dict.fromkeys(social_pages + list(fb.get("social_pages", [])))),
                    "email_sources": email_sources,
                    "phone_sources": phone_sources,
                    "social_link_sources": social_sources,
                    "used_js_fallback": True,
                }

        return {
            "text": combined_text,
            "emails": emails_unique,
            "phones": phones_unique,
            "pages_scraped": pages_scraped,
            "social_links": social_links,
            "social_pages": social_pages,
            "email_sources": email_sources,
            "phone_sources": phone_sources,
            "social_link_sources": social_sources,
            "website_valid": True,
        }

    def _try_js_fallback(self, url: str, reason: str) -> dict[str, Any]:
        if self.js_fallback is None:
            return _empty_crawl_result()
        logger.info("Using rendered fallback for %s because %s", url, reason)
        result = self.js_fallback.crawl(url)
        text = str(result.get("text", ""))
        html_pages = list(result.get("html_pages", []))
        if not text and not html_pages:
            return _empty_crawl_result()

        all_text: list[str] = []
        all_emails: list[str] = []
        all_phones: list[str] = []
        email_sources: dict[str, list[str]] = {}
        phone_sources: dict[str, list[str]] = {}
        social_candidates: dict[str, list[str]] = {}
        social_sources: dict[str, dict[str, list[str]]] = {}
        social_pages: list[str] = []

        for index, page in enumerate(html_pages, start=1):
            page_html = str(page.get("html", ""))
            page_url = normalize_website(str(page.get("url", ""))) or url
            page_label = _label_for_page(page_url, url, default=f"rendered_page_{index}")
            parsed = self._parse_page(page_html, page_url, page_label, email_sources, phone_sources)
            all_text.append(parsed.text)
            all_emails.extend(parsed.emails)
            all_phones.extend(parsed.phones)
            _merge_social_extraction(social_candidates, social_sources, parsed.social)
            social_pages.append(page_label)

        if text and not all_text:
            parsed = self._parse_page(text, url, "rendered_text", email_sources, phone_sources)
            all_text.append(parsed.text)
            all_emails.extend(parsed.emails)
            all_phones.extend(parsed.phones)
            _merge_social_extraction(social_candidates, social_sources, parsed.social)

        return {
            "text": "\n\n".join(filter(None, [*all_text, text]))[:40_000],
            "emails": list(dict.fromkeys(all_emails)),
            "phones": list(dict.fromkeys(all_phones)),
            "pages_scraped": int(result.get("pages_scraped", 0)),
            "social_links": flatten_social_links(social_candidates),
            "social_pages": list(dict.fromkeys(social_pages)),
            "email_sources": email_sources,
            "phone_sources": phone_sources,
            "social_link_sources": social_sources,
            "used_js_fallback": True,
        }

    def _fetch(self, url: str) -> str | None:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LeadBot/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:
                raw = resp.read(500_000)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:
            logger.warning("Static website fetch failed for %s: %s", url, exc)
            return None

    def _parse_page(
        self,
        html: str,
        page_url: str,
        page_label: str,
        email_sources: dict[str, list[str]],
        phone_sources: dict[str, list[str]],
    ) -> ParsedPage:
        text, emails, phones = self._parse(
            html,
            page_url,
            page_label,
            email_sources,
            phone_sources,
        )
        return ParsedPage(
            text=text,
            emails=emails,
            phones=phones,
            social=extract_social_links_with_sources(html, page_url, page_label),
        )

    def _fetch_target_page(
        self,
        homepage_html: str,
        homepage_url: str,
        page_name: str,
        slugs: tuple[str, ...],
        visited: set[str],
    ) -> tuple[str, str] | None:
        for candidate in _page_candidates(homepage_html, homepage_url, page_name, slugs):
            if candidate in visited:
                continue
            html = self._fetch(candidate)
            if html is not None:
                return candidate, html
        return None

    def _parse(
        self,
        html: str,
        page_url: str = "",
        page_label: str = "page",
        email_sources: dict[str, list[str]] | None = None,
        phone_sources: dict[str, list[str]] | None = None,
    ) -> tuple[str, list[str], list[str]]:
        cf_emails = [_decode_cf_email(m) for m in CF_EMAIL_RE.findall(html)]

        mailto_emails = re.findall(r'href=["\']mailto:([^"\'?\s]+)', html, re.IGNORECASE)

        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        else:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

        emails = list(dict.fromkeys(cf_emails + mailto_emails + EMAIL_RE.findall(text)))
        emails = list(dict.fromkeys(filter(None, (normalize_email(e) for e in emails))))
        phones = list(dict.fromkeys(filter(None, (normalize_phone(p) for p in PHONE_RE.findall(text)))))
        if email_sources is not None:
            for email in emails:
                add_source(email_sources, email, f"{page_label}:{page_url or 'html'}")
        if phone_sources is not None:
            for phone in phones:
                add_source(phone_sources, phone, f"{page_label}:{page_url or 'html'}")
        return text[:20_000], emails, phones


def _looks_js_rendered(text: str, emails: list[str], phones: list[str]) -> bool:
    if len(text) < 600:
        return True
    if len(text) < 2000 and not emails and not phones:
        return True
    return False


def _empty_crawl_result() -> dict[str, Any]:
    return {
        "text": "",
        "emails": [],
        "phones": [],
        "pages_scraped": 0,
        "social_links": {},
        "social_pages": [],
        "email_sources": {},
        "phone_sources": {},
        "social_link_sources": {},
    }


def _label_for_page(page_url: str, homepage_url: str, default: str) -> str:
    lowered = page_url.lower()
    if _same_site(page_url, homepage_url):
        if "contact" in lowered:
            return "rendered_contact"
        if "about" in lowered:
            return "rendered_about"
        return "rendered_homepage"
    return default


def _merge_social_extraction(
    target: dict[str, list[str]],
    source_map: dict[str, dict[str, list[str]]],
    extraction: SocialExtraction,
) -> None:
    merge_social_candidates(target, extraction.links)
    merge_social_source_map(source_map, extraction.sources)


def _page_candidates(homepage_html: str, homepage_url: str, page_name: str, slugs: tuple[str, ...]) -> list[str]:
    candidates = _linked_pages(homepage_html, homepage_url, page_name)
    candidates.extend(urljoin(homepage_url, f"/{slug}") for slug in slugs)
    return list(dict.fromkeys(candidate for candidate in candidates if _same_site(candidate, homepage_url)))


def _linked_pages(html: str, homepage_url: str, page_name: str) -> list[str]:
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        hrefs = [
            str(anchor.get("href", ""))
            for anchor in soup.find_all("a", href=True)
            if page_name in anchor.get_text(" ", strip=True).lower()
            or page_name in str(anchor.get("href", "")).lower()
        ]
    else:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        hrefs = [href for href in hrefs if page_name in href.lower()]
    return [urljoin(homepage_url, href) for href in hrefs]


def _same_site(candidate: str, homepage_url: str) -> bool:
    try:
        return urlparse(candidate).netloc.lower() == urlparse(homepage_url).netloc.lower()
    except ValueError:
        return False


def _decode_cf_email(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
    except Exception:
        return ""
