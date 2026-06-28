from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .confidence import (
    DiscoveryIdentity,
    email_candidate_confidence,
    is_high_confidence,
    social_candidate_confidence,
)
from .models import PlaceLead, merge_unique
from .social_links import SOCIAL_NETWORKS, social_network_for_url
from .validation import normalize_email

APIFY_BASE = "https://api.apify.com/v2"
APIFY_START_TIMEOUT_SECONDS = 60
APIFY_POLL_TIMEOUT_SECONDS = 45
APIFY_DATASET_TIMEOUT_SECONDS = 90
APIFY_MAX_HTTP_ATTEMPTS = 3
APIFY_MAX_RUN_WAIT_SECONDS = 600
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
logger = logging.getLogger(__name__)

SEGMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "design_build": ("design-build", "design build", "landscape construction", "landscape installation"),
    "commercial_contractor": ("commercial landscape", "commercial grounds", "grounds management", "commercial projects"),
    "landscape_architecture": ("landscape architect", "landscape architecture", "site planning", "sustainable design"),
    "green_roof": ("green roof", "living roof", "eco roof", "living wall", "vertical garden"),
    "high_end_residential": ("luxury landscape", "estate landscaping", "custom outdoor living", "high-end landscape"),
    "materials_distributor": ("wholesale", "supply yard", "landscape supply", "bulk landscaping", "distributor"),
}


class ApifyMapsClient:
    def __init__(self, api_token: str, actor_id: str) -> None:
        self.api_token = api_token
        self.actor_id = actor_id.replace("/", "~")

    def search_one(
        self,
        query: str,
        location: str,
        max_results: int = 50,
        seen_place_ids: set[str] | None = None,
        website_filter: str = "withWebsite",
    ) -> list[PlaceLead]:
        if seen_place_ids is None:
            seen_place_ids = set()
        include_web_results = website_filter == "withoutWebsite"
        run_input = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": max(1, max_results),
            "placeMinimumStars": "three",
            "skipClosedPlaces": True,
            "website": website_filter,
            "searchMatching": "all",
            "maxReviews": 0,
            "maxImages": 0,
            "scrapeContacts": True,
            "scrapePlaceDetailPage": include_web_results,
            "includeWebResults": include_web_results,
            "maximumLeadsEnrichmentRecords": 0,
        }
        logger.info(
            "Google Maps search executed: query=%r location=%r website_filter=%s "
            "web_results_requested=%s",
            query,
            location,
            website_filter,
            include_web_results,
        )
        raw = self._run_actor(run_input)
        logger.info(
            "Google Maps search completed: query=%r raw_leads=%s",
            query,
            len(raw),
        )
        leads = []
        for item in raw:
            lead = self._normalize(item)
            if lead.place_id and lead.place_id in seen_place_ids:
                continue
            if lead.place_id:
                seen_place_ids.add(lead.place_id)
            lead.search_query = query
            leads.append(lead)
        return leads

    def _run_actor(self, run_input: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE}/acts/{self.actor_id}/runs?token={self.api_token}"
        body = json.dumps(run_input).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        run_data = _read_json_with_retries(req, APIFY_START_TIMEOUT_SECONDS, "start Apify Google Maps actor")
        run_id = run_data["data"]["id"]
        dataset_id = run_data["data"]["defaultDatasetId"]
        logger.info("Started Apify Google Maps run %s with dataset %s", run_id, dataset_id)
        self._wait_for_run(run_id)
        return self._fetch_dataset(dataset_id)

    def _wait_for_run(
        self,
        run_id: str,
        poll_seconds: int = 5,
        max_wait: int = APIFY_MAX_RUN_WAIT_SECONDS,
    ) -> None:
        url = f"{APIFY_BASE}/actor-runs/{run_id}?token={self.api_token}"
        deadline = time.monotonic() + max_wait
        last_status = "UNKNOWN"
        while time.monotonic() < deadline:
            try:
                data = _read_json_with_retries(url, APIFY_POLL_TIMEOUT_SECONDS, f"poll Apify run {run_id}")
            except (TimeoutError, urllib.error.URLError) as exc:
                logger.warning("Apify run %s status poll timed out; continuing to wait: %s", run_id, exc)
                time.sleep(poll_seconds)
                continue
            status = data["data"]["status"]
            if status != last_status:
                logger.info("Apify run %s status: %s", run_id, status)
                last_status = status
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
                return
            time.sleep(poll_seconds)
        raise TimeoutError(f"Apify run {run_id} did not finish within {max_wait}s")

    def _fetch_dataset(self, dataset_id: str) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE}/datasets/{dataset_id}/items?token={self.api_token}&format=json"
        return _read_json_with_retries(url, APIFY_DATASET_TIMEOUT_SECONDS, f"fetch Apify dataset {dataset_id}")

    def _normalize(self, item: dict[str, Any]) -> PlaceLead:
        def get(*keys: str, default: Any = "") -> Any:
            for k in keys:
                v = item.get(k)
                if v is not None:
                    return v
            return default

        name = get("title", "name", "businessName", default="")
        website = get("website", "websiteUrl", "webSite", default="")
        address = get("address", "formattedAddress", default="")
        city = get("city", default="")
        state = get("state", "region", default="")
        country = get("country", default="")
        phone = get("phone", "phoneUnformatted", default="")
        emails = _extract_values(item, ("emails", "email", "contactEmails", "emailsUncertain"))
        direct_emails = list(emails)
        phones = _extract_values(item, ("phones", "phoneNumbers", "contactPhones"))
        social_links = _extract_social_links(item, website)
        maps_url = get("url", "googleMapsUrl", "placeUrl", default="")
        place_id = get("placeId", "id", default="")
        rating = get("totalScore", "rating", default=None)
        review_count = get("reviewsCount", "userRatingsTotal", default=None)
        identity = DiscoveryIdentity(
            business_name=str(name),
            address=str(address),
            city=str(city),
            state=str(state),
            country=str(country),
            phone=str(phone),
            website=str(website),
            google_maps_url=str(maps_url),
        )
        (
            web_emails,
            web_social_links,
            web_email_confidence,
            web_social_confidence,
            web_source_notes,
        ) = _extract_web_result_contacts(item, identity)
        emails = merge_unique(emails, web_emails)
        email_confidence = {
            normalized: 0.95
            for value in direct_emails
            if (normalized := normalize_email(value))
        }
        for value, confidence in web_email_confidence.items():
            email_confidence[value] = max(email_confidence.get(value, 0.0), confidence)

        social_confidence = {
            network: {url: 0.93}
            for network, url in social_links.items()
        }
        for network, url in web_social_links.items():
            confidence = web_social_confidence.get(network, {}).get(url, 0.0)
            existing = social_links.get(network)
            existing_confidence = (
                social_confidence.get(network, {}).get(existing, 0.0)
                if existing
                else 0.0
            )
            if not existing or confidence > existing_confidence:
                social_links[network] = url
            social_confidence.setdefault(network, {})[url] = confidence

        description = " ".join(filter(None, [
            str(get("categoryName", "categories", default="")),
            str(get("description", default="")),
            name,
        ])).lower()

        segment = _infer_segment(description)
        logger.info(
            "Lead parsed: business=%r website_found=%s email_count=%s phone_found=%s "
            "socials_found=%s google_web_results=%s",
            name,
            bool(website),
            len(emails),
            bool(phone or phones),
            sorted(social_links),
            len(item.get("webResults") or []),
        )

        return PlaceLead(
            place_id=str(place_id),
            business_name=str(name),
            website=str(website),
            google_maps_url=str(maps_url),
            address=str(address),
            city=str(city),
            state=str(state),
            country=str(country),
            phone=str(phone),
            rating=float(rating) if rating is not None else None,
            user_rating_count=int(review_count) if review_count is not None else None,
            lead_segment=segment,
            raw_emails=emails,
            raw_phones=phones,
            social_links=social_links,
            email_confidence=email_confidence,
            social_confidence=social_confidence,
            social_status="found" if social_links else "missing",
            source_notes=web_source_notes,
        )


def _infer_segment(text: str) -> str:
    for segment, keywords in SEGMENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return segment
    return "unknown"


def _extract_values(item: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = item.get(key)
        if not raw:
            continue
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, str):
                    values.append(entry)
                elif isinstance(entry, dict):
                    value = entry.get("email") or entry.get("phone") or entry.get("value")
                    if value:
                        values.append(str(value))
    return list(dict.fromkeys(v.strip() for v in values if v and str(v).strip()))


def _extract_social_links(item: dict[str, Any], website: str = "") -> dict[str, str]:
    candidates: list[str] = [website]
    for key in (
        "socialLinks",
        "socialMedia",
        "socials",
        "facebook",
        "facebookUrl",
        "facebooks",
        "instagram",
        "instagramUrl",
        "instagrams",
        "linkedin",
        "linkedinUrl",
        "linkedIn",
        "linkedIns",
        "twitter",
        "twitterUrl",
        "twitters",
        "x",
        "xUrl",
        "youtube",
        "youtubeUrl",
        "youtubes",
        "tiktok",
        "tiktokUrl",
        "tiktoks",
        "whatsapp",
        "whatsappUrl",
        "whatsapps",
    ):
        candidates.extend(_flatten_candidate_values(item.get(key)))

    result: dict[str, str] = {}
    for value in candidates:
        network = social_network_for_url(value)
        if network in SOCIAL_NETWORKS and network not in result:
            result[network] = value
    return result


def _extract_web_result_contacts(
    item: dict[str, Any],
    identity: DiscoveryIdentity,
) -> tuple[
    list[str],
    dict[str, str],
    dict[str, float],
    dict[str, dict[str, float]],
    list[str],
]:
    emails: list[str] = []
    social_links: dict[str, str] = {}
    email_confidence: dict[str, float] = {}
    social_confidence: dict[str, dict[str, float]] = {}
    source_notes: list[str] = []

    for entry in item.get("webResults") or []:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        title = str(entry.get("title") or "")
        description = str(entry.get("description") or "")
        displayed_url = str(entry.get("displayedUrl") or "")
        evidence = " ".join((title, description, displayed_url, url))
        source = f"apify_google_maps_web_result:{url or title or 'unknown'}"

        for match in EMAIL_RE.findall(evidence):
            email = normalize_email(match)
            if not email:
                continue
            confidence = email_candidate_confidence(email, evidence, identity, url)
            if not is_high_confidence(confidence):
                logger.info(
                    "Google web result rejected email for %s: %s score=%.3f source=%s",
                    identity.business_name,
                    email,
                    confidence,
                    source,
                )
                continue
            emails = merge_unique(emails, [email])
            email_confidence[email] = max(
                email_confidence.get(email, 0.0),
                confidence,
            )
            source_notes = merge_unique(
                source_notes,
                [f"email found via {source} confidence={confidence:.3f}: {email}"],
            )
            logger.info(
                "Google web result found email for %s: %s score=%.3f source=%s",
                identity.business_name,
                email,
                confidence,
                source,
            )

        network = social_network_for_url(url)
        if network not in SOCIAL_NETWORKS:
            continue
        confidence = social_candidate_confidence(url, evidence, identity)
        if not is_high_confidence(confidence):
            logger.info(
                "Google web result rejected %s for %s: %s score=%.3f source=%s",
                network,
                identity.business_name,
                url,
                confidence,
                source,
            )
            continue
        existing = social_links.get(network)
        existing_confidence = (
            social_confidence.get(network, {}).get(existing, 0.0)
            if existing
            else 0.0
        )
        if not existing or confidence > existing_confidence:
            social_links[network] = url
        social_confidence.setdefault(network, {})[url] = confidence
        source_notes = merge_unique(
            source_notes,
            [
                f"{network} found via {source} confidence={confidence:.3f}: {url}"
            ],
        )
        logger.info(
            "Google web result found %s for %s: %s score=%.3f source=%s",
            network,
            identity.business_name,
            url,
            confidence,
            source,
        )

    return (
        emails,
        social_links,
        email_confidence,
        social_confidence,
        source_notes,
    )


def _flatten_candidate_values(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for nested in value.values():
            values.extend(_flatten_candidate_values(nested))
        return values
    if isinstance(value, list):
        values: list[str] = []
        for nested in value:
            values.extend(_flatten_candidate_values(nested))
        return values
    return []


def _read_json_with_retries(request: Any, timeout: int, description: str) -> Any:
    last_exc: Exception | None = None
    for attempt in range(1, APIFY_MAX_HTTP_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code < 500 or attempt == APIFY_MAX_HTTP_ATTEMPTS:
                raise
            logger.warning(
                "Apify request failed while trying to %s; HTTP %s, attempt %s/%s",
                description,
                exc.code,
                attempt,
                APIFY_MAX_HTTP_ATTEMPTS,
            )
        except (TimeoutError, urllib.error.URLError) as exc:
            last_exc = exc
            if attempt == APIFY_MAX_HTTP_ATTEMPTS:
                raise
            logger.warning(
                "Apify request timed out while trying to %s; attempt %s/%s",
                description,
                attempt,
                APIFY_MAX_HTTP_ATTEMPTS,
            )
        time.sleep(min(10, attempt * 2))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Apify request failed while trying to {description}")
