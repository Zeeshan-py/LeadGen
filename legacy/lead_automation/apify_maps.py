"""Legacy Apify Google Maps integration client."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from .models import PlaceLead

APIFY_BASE = "https://api.apify.com/v2"

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
    ) -> list[PlaceLead]:
        if seen_place_ids is None:
            seen_place_ids = set()
        run_input = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": max(1, max_results),
            "placeMinimumStars": "three",
            "skipClosedPlaces": True,
            "website": "withWebsite",
            "searchMatching": "all",
            "maxReviews": 0,
            "maxImages": 0,
            "scrapeContacts": False,
            "scrapePlaceDetailPage": False,
            "maximumLeadsEnrichmentRecords": 0,
        }
        raw = self._run_actor(run_input)
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            run_data = json.loads(resp.read())
        run_id = run_data["data"]["id"]
        dataset_id = run_data["data"]["defaultDatasetId"]
        self._wait_for_run(run_id)
        return self._fetch_dataset(dataset_id)

    def _wait_for_run(self, run_id: str, poll_seconds: int = 5, max_wait: int = 300) -> None:
        url = f"{APIFY_BASE}/actor-runs/{run_id}?token={self.api_token}"
        waited = 0
        while waited < max_wait:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())
            status = data["data"]["status"]
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                if status != "SUCCEEDED":
                    raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
                return
            time.sleep(poll_seconds)
            waited += poll_seconds
        raise TimeoutError(f"Apify run {run_id} did not finish within {max_wait}s")

    def _fetch_dataset(self, dataset_id: str) -> list[dict[str, Any]]:
        url = f"{APIFY_BASE}/datasets/{dataset_id}/items?token={self.api_token}&format=json"
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())

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
        phone = get("phone", "phoneUnformatted", default="")
        maps_url = get("url", "googleMapsUrl", "placeUrl", default="")
        place_id = get("placeId", "id", default="")
        rating = get("totalScore", "rating", default=None)
        review_count = get("reviewsCount", "userRatingsTotal", default=None)

        description = " ".join(filter(None, [
            str(get("categoryName", "categories", default="")),
            str(get("description", default="")),
            name,
        ])).lower()

        segment = _infer_segment(description)

        return PlaceLead(
            place_id=str(place_id),
            business_name=str(name),
            website=str(website),
            google_maps_url=str(maps_url),
            address=str(address),
            phone=str(phone),
            rating=float(rating) if rating is not None else None,
            user_rating_count=int(review_count) if review_count is not None else None,
            lead_segment=segment,
        )


def _infer_segment(text: str) -> str:
    for segment, keywords in SEGMENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return segment
    return "unknown"
