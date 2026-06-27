from __future__ import annotations

import logging
import re
import ssl
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .confidence import (
    DiscoveryIdentity,
    email_candidate_confidence,
    google_business_candidate_confidence,
    is_high_confidence,
    social_candidate_confidence,
    website_candidate_confidence,
)
from .models import merge_unique
from .social_links import SOCIAL_NETWORKS, social_network_for_url
from .source_maps import merge_social_source_map, merge_source_map
from .validation import normalize_email, normalize_phone, normalize_website

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


SEARCH_URL = "https://duckduckgo.com/html/"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().\-]{6,}\d)")
SEARCH_GROUPS = (
    ("general", "email phone contact facebook instagram linkedin youtube tiktok twitter whatsapp"),
    ("email", "email contact"),
    ("social_primary", "facebook instagram"),
    ("social_professional", "linkedin youtube"),
    ("social_other", "tiktok twitter whatsapp"),
    ("google_business", "google maps"),
)
BLOCKED_WEBSITE_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "whatsapp.com",
    "wa.me",
    "google.com",
    "maps.google.",
    "maps.app.goo.gl",
    "g.page",
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
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    url: str
    text: str


@dataclass
class ContactDiscoveryResult:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: dict[str, list[str]] = field(default_factory=dict)
    website_candidates: list[str] = field(default_factory=list)
    google_business_links: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    email_sources: dict[str, list[str]] = field(default_factory=dict)
    phone_sources: dict[str, list[str]] = field(default_factory=dict)
    social_sources: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    google_business_sources: dict[str, list[str]] = field(default_factory=dict)
    email_confidence: dict[str, float] = field(default_factory=dict)
    social_confidence: dict[str, dict[str, float]] = field(default_factory=dict)
    website_confidence: dict[str, float] = field(default_factory=dict)
    google_business_confidence: dict[str, float] = field(default_factory=dict)


class ContactDiscovery:
    def __init__(self, timeout_seconds: int = 12, max_results: int = 8) -> None:
        self.timeout = timeout_seconds
        self.max_results = max(1, max_results)
        self._ssl_ctx = ssl.create_default_context()

    def search_business(
        self,
        business_name: str,
        location: str,
        business_type: str = "",
        *,
        address: str = "",
        city: str = "",
        state: str = "",
        country: str = "",
        phone: str = "",
        website: str = "",
        google_maps_url: str = "",
        exhaustive: bool = False,
    ) -> ContactDiscoveryResult:
        identity = DiscoveryIdentity(
            business_name=business_name,
            address=address or location,
            city=city,
            state=state,
            country=country,
            phone=phone,
            website=website,
            google_maps_url=google_maps_url,
        )
        result = ContactDiscoveryResult()
        location_query = " ".join(
            dict.fromkeys(
                part.strip()
                for part in (city, state, country, location)
                if part and part.strip()
            )
        )

        query_specs = [
            (
                query_label,
                " ".join(
                    part
                    for part in (
                        f'"{business_name}"',
                        location_query,
                        business_type,
                        (
                            phone
                            if query_label in {"general", "google_business"}
                            else ""
                        ),
                        search_terms,
                    )
                    if part
                ),
            )
            for query_label, search_terms in SEARCH_GROUPS
        ]

        if exhaustive:
            for query_label, _query in query_specs:
                logger.info(
                    "Contact discovery searching %s for %s with query group %s",
                    SEARCH_URL,
                    business_name,
                    query_label,
                )
            with ThreadPoolExecutor(
                max_workers=min(3, len(query_specs)),
                thread_name_prefix="contact-discovery",
            ) as executor:
                fetched = [
                    (query_label, executor.submit(self._fetch_search, query))
                    for query_label, query in query_specs
                ]
                for query_label, future in fetched:
                    self._merge_query_result(
                        result,
                        future.result(),
                        identity,
                        business_name,
                        query_label,
                    )
            _rank_result(result)
            return result

        for query_label, query in query_specs:
            logger.info(
                "Contact discovery searching %s for %s with query group %s",
                SEARCH_URL,
                business_name,
                query_label,
            )
            html = self._fetch_search(query)
            self._merge_query_result(
                result,
                html,
                identity,
                business_name,
                query_label,
            )
            if _has_enough_contact(result, self.max_results):
                break

        _rank_result(result)
        return result

    def _merge_query_result(
        self,
        result: ContactDiscoveryResult,
        html: str,
        identity: DiscoveryIdentity,
        business_name: str,
        query_label: str,
    ) -> None:
        if not html:
            return
        parsed = self.parse_search_html(
            html,
            identity=identity,
            query_label=query_label,
        )
        _merge_result(result, parsed)
        logger.info(
            "Contact discovery group %s for %s found %s emails, %s phones, "
            "%s social profiles, %s websites, and %s Google Business links",
            query_label,
            business_name,
            len(parsed.emails),
            len(parsed.phones),
            sum(len(links) for links in parsed.social_links.values()),
            len(parsed.website_candidates),
            len(parsed.google_business_links),
        )

    def parse_search_html(
        self,
        html: str,
        *,
        identity: DiscoveryIdentity | None = None,
        query_label: str = "general",
    ) -> ContactDiscoveryResult:
        result = ContactDiscoveryResult()
        search_results = _extract_search_results(html)
        if not search_results:
            search_results = [
                SearchResult(url=url, text=_plain_text(html)[:5000])
                for url in _extract_result_urls(html)
            ]

        for search_result in search_results[: self.max_results]:
            normalized_url = normalize_website(search_result.url)
            if not normalized_url:
                continue
            result.source_urls = merge_unique(result.source_urls, [normalized_url])
            host = urllib.parse.urlsplit(normalized_url).netloc.lower().removeprefix("www.")
            source = f"duckduckgo:{query_label}:{host}"
            evidence = f"{search_result.text} {normalized_url}"

            for email in dict.fromkeys(
                normalize_email(match) for match in EMAIL_RE.findall(search_result.text)
            ):
                if not email:
                    continue
                confidence = email_candidate_confidence(
                    email,
                    evidence,
                    identity,
                    normalized_url,
                )
                self._add_email(result, email, source, confidence)

            identity_score = website_candidate_confidence(
                normalized_url,
                evidence,
                identity,
            )
            for phone in dict.fromkeys(
                normalize_phone(match) for match in PHONE_RE.findall(search_result.text)
            ):
                if phone and is_high_confidence(identity_score):
                    result.phones = merge_unique(result.phones, [phone])
                    result.phone_sources.setdefault(phone, []).append(source)

            network = social_network_for_url(normalized_url)
            if network in SOCIAL_NETWORKS:
                confidence = social_candidate_confidence(
                    normalized_url,
                    evidence,
                    identity,
                )
                self._add_social(result, network, normalized_url, source, confidence)
                continue

            if _looks_like_google_business_url(normalized_url):
                confidence = google_business_candidate_confidence(
                    normalized_url,
                    evidence,
                    identity,
                )
                self._add_google_business(
                    result,
                    normalized_url,
                    source,
                    confidence,
                )
                continue

            if _looks_like_business_website(normalized_url):
                confidence = website_candidate_confidence(
                    normalized_url,
                    evidence,
                    identity,
                )
                if is_high_confidence(confidence):
                    result.website_candidates = merge_unique(
                        result.website_candidates,
                        [normalized_url],
                    )
                    result.website_confidence[normalized_url] = max(
                        result.website_confidence.get(normalized_url, 0.0),
                        confidence,
                    )
                else:
                    logger.info(
                        "Rejected low-confidence website candidate %s (score %.3f)",
                        normalized_url,
                        confidence,
                    )
        _rank_result(result)
        return result

    def _add_email(
        self,
        result: ContactDiscoveryResult,
        email: str,
        source: str,
        confidence: float,
    ) -> None:
        if not is_high_confidence(confidence):
            logger.info(
                "Rejected low-confidence email candidate %s via %s (score %.3f)",
                email,
                source,
                confidence,
            )
            return
        result.emails = merge_unique(result.emails, [email])
        result.email_sources.setdefault(email, []).append(source)
        result.email_confidence[email] = max(
            result.email_confidence.get(email, 0.0),
            confidence,
        )
        logger.info(
            "Accepted email candidate %s via %s (score %.3f)",
            email,
            source,
            confidence,
        )

    def _add_social(
        self,
        result: ContactDiscoveryResult,
        network: str,
        url: str,
        source: str,
        confidence: float,
    ) -> None:
        if not is_high_confidence(confidence):
            logger.info(
                "Rejected low-confidence %s candidate %s via %s (score %.3f)",
                network,
                url,
                source,
                confidence,
            )
            return
        result.social_links[network] = merge_unique(
            result.social_links.get(network, []),
            [url],
        )
        result.social_sources.setdefault(network, {}).setdefault(url, []).append(source)
        result.social_confidence.setdefault(network, {})[url] = max(
            result.social_confidence.get(network, {}).get(url, 0.0),
            confidence,
        )
        logger.info(
            "Accepted %s candidate %s via %s (score %.3f)",
            network,
            url,
            source,
            confidence,
        )

    def _add_google_business(
        self,
        result: ContactDiscoveryResult,
        url: str,
        source: str,
        confidence: float,
    ) -> None:
        if not is_high_confidence(confidence):
            logger.info(
                "Rejected low-confidence Google Business candidate %s via %s (score %.3f)",
                url,
                source,
                confidence,
            )
            return
        result.google_business_links = merge_unique(
            result.google_business_links,
            [url],
        )
        result.google_business_sources.setdefault(url, []).append(source)
        result.google_business_confidence[url] = max(
            result.google_business_confidence.get(url, 0.0),
            confidence,
        )
        logger.info(
            "Accepted Google Business candidate %s via %s (score %.3f)",
            url,
            source,
            confidence,
        )

    def _fetch_search(self, query: str) -> str:
        params = urllib.parse.urlencode({"q": query})
        url = f"{SEARCH_URL}?{params}"
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; LeadForgeAI/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self._ssl_ctx,
            ) as response:
                raw = response.read(500_000)
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:
            logger.warning("Contact discovery search failed: %s", exc)
            return ""


def _extract_search_results(html: str) -> list[SearchResult]:
    if not HAS_BS4:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for container in soup.select(".result"):
        anchor = container.select_one("a.result__a") or container.find("a", href=True)
        if not anchor:
            continue
        url = _unwrap_search_href(str(anchor.get("href", "")))
        if not url:
            continue
        text = container.get_text(" ", strip=True)
        if url not in seen_urls:
            results.append(SearchResult(url=url, text=text))
            seen_urls.add(url)
    return results


def _extract_result_urls(html: str) -> list[str]:
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


def _plain_text(html: str) -> str:
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(" ", strip=True)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _unwrap_search_href(href: str) -> str:
    value = href.strip()
    if not value:
        return ""
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ""
    if (
        parsed.scheme in {"http", "https"}
        and parsed.netloc
        and "duckduckgo.com" not in parsed.netloc
    ):
        return value
    query = urllib.parse.parse_qs(parsed.query)
    uddg = query.get("uddg", [""])[0]
    if uddg:
        return urllib.parse.unquote(uddg)
    if value.startswith("//duckduckgo.com/l/"):
        parsed = urllib.parse.urlsplit(f"https:{value}")
        return urllib.parse.unquote(
            urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        )
    return ""


def _looks_like_google_business_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if host in {"maps.app.goo.gl", "g.page"}:
        return bool(path.strip("/"))
    return (
        (host == "google.com" or host.endswith(".google.com")) and "/maps" in path
    ) or host.startswith("maps.google.")


def _looks_like_business_website(url: str) -> bool:
    try:
        host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return False
    return bool(host) and not any(
        host == blocked or blocked in host
        for blocked in BLOCKED_WEBSITE_HOSTS
    )


def _merge_result(
    target: ContactDiscoveryResult,
    source: ContactDiscoveryResult,
) -> None:
    target.emails = merge_unique(target.emails, source.emails)
    target.phones = merge_unique(target.phones, source.phones)
    target.website_candidates = merge_unique(
        target.website_candidates,
        source.website_candidates,
    )
    target.google_business_links = merge_unique(
        target.google_business_links,
        source.google_business_links,
    )
    target.source_urls = merge_unique(target.source_urls, source.source_urls)
    merge_source_map(target.email_sources, source.email_sources)
    merge_source_map(target.phone_sources, source.phone_sources)
    merge_source_map(
        target.google_business_sources,
        source.google_business_sources,
    )
    merge_social_source_map(target.social_sources, source.social_sources)
    for network, links in source.social_links.items():
        target.social_links[network] = merge_unique(
            target.social_links.get(network, []),
            links,
        )
    _merge_confidence(target.email_confidence, source.email_confidence)
    _merge_confidence(target.website_confidence, source.website_confidence)
    _merge_confidence(
        target.google_business_confidence,
        source.google_business_confidence,
    )
    for network, scores in source.social_confidence.items():
        _merge_confidence(
            target.social_confidence.setdefault(network, {}),
            scores,
        )


def _merge_confidence(target: dict[str, float], source: dict[str, float]) -> None:
    for value, confidence in source.items():
        target[value] = max(target.get(value, 0.0), confidence)


def _rank_result(result: ContactDiscoveryResult) -> None:
    result.emails.sort(
        key=lambda value: result.email_confidence.get(value, 0.0),
        reverse=True,
    )
    result.website_candidates.sort(
        key=lambda value: result.website_confidence.get(value, 0.0),
        reverse=True,
    )
    result.google_business_links.sort(
        key=lambda value: result.google_business_confidence.get(value, 0.0),
        reverse=True,
    )
    for network, links in result.social_links.items():
        scores = result.social_confidence.get(network, {})
        links.sort(key=lambda value: scores.get(value, 0.0), reverse=True)


def _has_enough_contact(
    result: ContactDiscoveryResult,
    max_results: int,
) -> bool:
    social_count = sum(len(links) for links in result.social_links.values())
    return (
        bool((result.emails or result.phones) and social_count)
        or social_count >= 2
        or len(result.source_urls) >= max_results
    )
