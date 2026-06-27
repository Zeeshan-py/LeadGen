from __future__ import annotations

import html as html_lib
import re
import json
from dataclasses import dataclass, field
from collections.abc import Iterable
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


SOCIAL_NETWORKS = (
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "x_twitter",
    "tiktok",
    "whatsapp",
)

SOCIAL_DOMAINS = {
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com",),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com",),
    "x_twitter": ("x.com", "twitter.com"),
    "tiktok": ("tiktok.com",),
    "whatsapp": ("whatsapp.com", "wa.me"),
}

HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
URL_RE = re.compile(r"https?:\\?/\\?/[^\"'<>\\\s),]+", re.IGNORECASE)
SHARE_PATH_MARKERS = ("/share", "/sharer", "/intent", "/tweet", "/plugins/", "/dialog/")
CONTENT_PATH_MARKERS = (
    "/p/",
    "/reel/",
    "/posts/",
    "/status/",
    "/watch",
    "/shorts/",
    "/video/",
)
GENERIC_PATHS = {
    "",
    "/",
    "/home",
    "/login",
    "/privacy",
    "/terms",
    "/business",
    "/pages",
    "/explore",
    "/about",
}


@dataclass
class SocialExtraction:
    links: dict[str, list[str]] = field(default_factory=dict)
    sources: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def add(self, network: str, url: str, source: str) -> None:
        bucket = self.links.setdefault(network, [])
        if url not in bucket:
            bucket.append(url)
        source_bucket = self.sources.setdefault(network, {}).setdefault(url, [])
        if source and source not in source_bucket:
            source_bucket.append(source)


def extract_social_links(html: str, page_url: str) -> dict[str, list[str]]:
    return extract_social_links_with_sources(html, page_url).links


def extract_social_links_with_sources(html: str, page_url: str, page_label: str = "page") -> SocialExtraction:
    found = SocialExtraction()
    for href, source in _candidate_links_from_html(html, page_url, page_label):
        normalized = _absolute_http_url(href, page_url)
        network = social_network_for_url(normalized)
        if network:
            found.add(network, normalized, source)
    return found


def social_network_for_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    if (
        not host
        or path in GENERIC_PATHS
        or any(marker in path for marker in SHARE_PATH_MARKERS)
        or any(marker in path for marker in CONTENT_PATH_MARKERS)
    ):
        return None
    for network, domains in SOCIAL_DOMAINS.items():
        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
            if network == "whatsapp" and not _valid_whatsapp_url(parsed):
                return None
            return network
    return None


def flatten_social_links(values: dict[str, Iterable[str]]) -> dict[str, list[str]]:
    return {
        network: list(dict.fromkeys(str(link).strip() for link in links if str(link).strip()))
        for network, links in values.items()
        if network in SOCIAL_NETWORKS
    }


def merge_social_candidates(target: dict[str, list[str]], source: object) -> None:
    if not isinstance(source, dict):
        return
    for network, links in source.items():
        if network not in SOCIAL_NETWORKS:
            continue
        values = links if isinstance(links, list) else [links]
        bucket = target.setdefault(network, [])
        bucket.extend(
            value
            for value in (str(link).strip() for link in values)
            if value and value not in bucket
        )


def merged_social_candidates(*sources: object) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for source in sources:
        merge_social_candidates(merged, source)
    return merged


def select_social_links(
    candidates: dict[str, list[str]],
    confidence: dict[str, dict[str, float]] | None = None,
    min_confidence: float = 0.0,
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for network in SOCIAL_NETWORKS:
        valid = [
            value
            for value in candidates.get(network, [])
            if social_network_for_url(value) == network
        ]
        if not valid:
            continue
        scores = (confidence or {}).get(network, {})
        ranked = sorted(
            enumerate(valid),
            key=lambda item: (-scores.get(item[1], 0.0), item[0]),
        )
        best = ranked[0][1]
        if confidence is not None and scores.get(best, 0.0) < min_confidence:
            continue
        selected[network] = best
    return selected


def _valid_whatsapp_url(parsed: object) -> bool:
    host = str(getattr(parsed, "netloc", "")).lower().removeprefix("www.")
    path = str(getattr(parsed, "path", "")).strip("/")
    query = str(getattr(parsed, "query", ""))
    if host == "wa.me":
        digits = "".join(character for character in path if character.isdigit())
        return 7 <= len(digits) <= 15
    if path.lower() == "send":
        phone = parse_qs(query).get("phone", [""])[0]
        digits = "".join(character for character in phone if character.isdigit())
        return 7 <= len(digits) <= 15
    return path.lower().startswith(("channel/", "business/"))


def _candidate_links_from_html(html: str, page_url: str, page_label: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", ""))
            area = _dom_area(anchor)
            values.append((href, f"{page_label}:{area}:href"))
        for meta in soup.find_all("meta"):
            content = str(meta.get("content", ""))
            source_name = str(meta.get("property") or meta.get("name") or "meta")
            for url in _urls_from_text(content):
                values.append((url, f"{page_label}:meta:{source_name}"))
        for script in soup.find_all("script"):
            script_type = str(script.get("type", "script")).lower() or "script"
            text = script.get_text(" ", strip=True)
            for url in _urls_from_text(text):
                values.append((url, f"{page_label}:{script_type}"))
        values.extend((url, f"{page_label}:json-ld:sameAs") for url in _schema_same_as_links(html))
        return values
    values.extend((href, f"{page_label}:href") for href in HREF_RE.findall(html))
    values.extend((url, f"{page_label}:script-data") for url in _urls_from_text(html))
    return values


def _dom_area(tag: object) -> str:
    if not HAS_BS4:
        return "body"
    parent = tag
    while parent is not None:
        name = getattr(parent, "name", "")
        if name in {"header", "footer", "nav"}:
            return str(name)
        parent = getattr(parent, "parent", None)
    return "body"


def _urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    cleaned = html_lib.unescape(text).replace("\\/", "/")
    return list(dict.fromkeys(match.rstrip(".,;") for match in URL_RE.findall(cleaned)))


def _schema_same_as_links(html: str) -> list[str]:
    values: list[str] = []
    if not HAS_BS4:
        return values
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (json.JSONDecodeError, TypeError):
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                same_as = item.get("sameAs", [])
                if isinstance(same_as, str):
                    values.append(same_as)
                elif isinstance(same_as, list):
                    values.extend(str(value) for value in same_as)
                stack.extend(value for value in item.values() if isinstance(value, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)
    return values


def _absolute_http_url(href: str, page_url: str) -> str:
    candidate = urljoin(page_url, html_lib.unescape(href.strip()).replace("\\/", "/"))
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
