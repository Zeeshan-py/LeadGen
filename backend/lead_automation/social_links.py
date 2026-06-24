from __future__ import annotations

import re
import json
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

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
)

SOCIAL_DOMAINS = {
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com",),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com", "youtu.be"),
    "x_twitter": ("x.com", "twitter.com"),
    "tiktok": ("tiktok.com",),
}

HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)
SHARE_PATH_MARKERS = ("/share", "/sharer", "/intent", "/tweet")


def extract_social_links(html: str, page_url: str) -> dict[str, list[str]]:
    links = _hrefs_from_html(html) + _schema_same_as_links(html)
    found: dict[str, list[str]] = {network: [] for network in SOCIAL_NETWORKS}
    for href in links:
        normalized = _absolute_http_url(href, page_url)
        network = social_network_for_url(normalized)
        if network and normalized not in found[network]:
            found[network].append(normalized)
    return {network: values for network, values in found.items() if values}


def social_network_for_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if not host or any(marker in path for marker in SHARE_PATH_MARKERS):
        return None
    for network, domains in SOCIAL_DOMAINS.items():
        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return network
    return None


def flatten_social_links(values: dict[str, Iterable[str]]) -> dict[str, list[str]]:
    return {
        network: list(dict.fromkeys(str(link).strip() for link in links if str(link).strip()))
        for network, links in values.items()
        if network in SOCIAL_NETWORKS
    }


def _hrefs_from_html(html: str) -> list[str]:
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        return [str(anchor.get("href", "")) for anchor in soup.find_all("a", href=True)]
    return HREF_RE.findall(html)


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
    candidate = urljoin(page_url, href.strip())
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
