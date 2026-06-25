from __future__ import annotations

import re
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .social_links import SOCIAL_NETWORKS, social_network_for_url
from .validation import normalize_website

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


SEARCH_URL = "https://duckduckgo.com/html/"
BLOCKED_WEBSITE_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "google.com",
    "maps.google.",
    "yelp.com",
    "tripadvisor.",
    "opentable.",
    "doordash.",
    "ubereats.",
    "grubhub.",
    "seamless.",
    "restaurantji.",
    "yellowpages.",
    "mapquest.",
    "foursquare.",
    "wikipedia.",
    "wixsite.com",
    "duckduckgo.com",
)


@dataclass
class ContactDiscoveryResult:
    emails: list[str] = field(default_factory=list)
    social_links: dict[str, list[str]] = field(default_factory=dict)
    website_candidates: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


class ContactDiscovery:
    def __init__(self, timeout_seconds: int = 12, max_results: int = 8) -> None:
        self.timeout = timeout_seconds
        self.max_results = max(1, max_results)
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def search_business(self, business_name: str, location: str, business_type: str = "") -> ContactDiscoveryResult:
        query = " ".join(
            part
            for part in (
                f'"{business_name}"',
                location,
                business_type,
                "email OR contact OR facebook OR instagram OR linkedin",
            )
            if part
        )
        html = self._fetch_search(query)
        if not html:
            return ContactDiscoveryResult()
        return self.parse_search_html(html)

    def parse_search_html(self, html: str) -> ContactDiscoveryResult:
        result = ContactDiscoveryResult()

        for url in _extract_result_urls(html):
            if len(result.source_urls) >= self.max_results:
                break
            normalized = normalize_website(url)
            if not normalized:
                continue
            result.source_urls.append(normalized)
            network = social_network_for_url(normalized)
            if network in SOCIAL_NETWORKS:
                bucket = result.social_links.setdefault(network, [])
                if normalized not in bucket:
                    bucket.append(normalized)
                continue
            if _looks_like_business_website(normalized) and normalized not in result.website_candidates:
                result.website_candidates.append(normalized)

        return result

    def _fetch_search(self, query: str) -> str:
        params = urllib.parse.urlencode({"q": query})
        url = f"{SEARCH_URL}?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; LeadForgeAI/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:
                raw = resp.read(500_000)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception:
            return ""


def _extract_result_urls(html: str) -> list[str]:
    hrefs: list[str] = []
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        hrefs = [str(anchor.get("href", "")) for anchor in soup.find_all("a", href=True)]
    else:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)

    urls: list[str] = []
    for href in hrefs:
        url = _unwrap_search_href(href)
        if url and url not in urls:
            urls.append(url)
    return urls


def _unwrap_search_href(href: str) -> str:
    value = href.strip()
    if not value:
        return ""
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme in {"http", "https"} and parsed.netloc and "duckduckgo.com" not in parsed.netloc:
        return value
    query = urllib.parse.parse_qs(parsed.query)
    uddg = query.get("uddg", [""])[0]
    if uddg:
        return urllib.parse.unquote(uddg)
    if value.startswith("//duckduckgo.com/l/"):
        parsed = urllib.parse.urlsplit(f"https:{value}")
        return urllib.parse.unquote(urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0])
    return ""


def _looks_like_business_website(url: str) -> bool:
    try:
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return False
    return bool(host) and not any(host == blocked or blocked in host for blocked in BLOCKED_WEBSITE_HOSTS)
