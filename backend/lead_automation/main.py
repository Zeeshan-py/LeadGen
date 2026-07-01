from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
from pathlib import Path
from urllib.error import URLError

from .apify_maps import ApifyMapsClient
from .apify_web import ApifyWebCrawler
from .ai_extractor import LeadExtractor
from .config import load_settings
from .coverage import CoverageTracker
from .models import PlaceLead, merge_unique
from .sheets import SheetsLeadStore
from .validation import qualifies_google_business
from .website_scraper import WebsiteScraper

MARKETS_PATH = Path("./coverage/canada_moss_markets.json")

POSITIVE_KEYWORDS = (
    "design-build",
    "design build",
    "landscape installation",
    "landscape construction",
    "landscape contractor",
    "custom outdoor living",
    "estate landscaping",
    "luxury landscape",
    "commercial landscape",
    "commercial grounds",
    "grounds management",
    "landscape architecture",
    "landscape architect",
    "site planning",
    "sustainable design",
    "green roof",
    "living roof",
    "eco roof",
    "living wall",
    "vertical garden",
    "hardscape",
    "softscape",
    "outdoor living",
)

NEGATIVE_KEYWORDS = (
    "lawn care",
    "lawn mowing",
    "grass cutting",
    "yard cleanup",
    "yard clean up",
    "weekly maintenance",
    "maintenance only",
    "tree service",
    "stump grinding",
    "sprinkler repair",
    "handyman",
    "pool cleaning",
    "snow removal only",
    "janitorial",
)

TARGET_SEGMENTS = {
    "design_build",
    "commercial_contractor",
    "high_end_residential",
    "landscape_architecture",
    "green_roof",
    "materials_distributor",
}


def main() -> int:
    args = parse_args()
    settings = load_settings()

    maps_client = ApifyMapsClient(
        api_token=settings.apify_api_token,
        actor_id=settings.apify_actor_id,
    )
    js_fallback = ApifyWebCrawler(api_token=settings.apify_api_token)
    scraper = WebsiteScraper(
        timeout_seconds=settings.fetch_timeout_seconds,
        max_pages=settings.max_website_pages,
        js_fallback=js_fallback,
    )
    extractor = LeadExtractor(api_key=settings.anthropic_api_key)
    tracker = CoverageTracker(settings.coverage_file)
    try:
        service_account_info = json.loads(settings.service_account_json)
    except json.JSONDecodeError as exc:
        print(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON; Google Sheets is unavailable.",
            file=sys.stderr,
        )
        return 1
    if not isinstance(service_account_info, dict):
        print(
            "GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object; Google Sheets is unavailable.",
            file=sys.stderr,
        )
        return 1
    store = SheetsLeadStore(
        service_account_info=service_account_info,
        spreadsheet_id=args.spreadsheet_id or settings.spreadsheet_id,
        sheet_name=args.sheet_name or settings.sheet_name,
    )

    market_name = args.market
    market_data = load_market(market_name)
    queries = market_data["queries"]
    location = market_data["location"]

    if tracker.is_complete(market_name) and not args.force:
        print(f"Market '{market_name}' already complete. Use --force to re-run.", file=sys.stderr)
        return 0

    print(f"Running {len(queries)} queries for '{market_name}' ({location})", file=sys.stderr)

    existing_keys = store.existing_dedupe_keys()
    seen_place_ids: set[str] = set()
    total_written = 0
    results_per_query = max(10, args.max_results // max(len(queries), 1))

    for query in queries:
        print(f"  query: {query!r}", file=sys.stderr)
        raw_leads = maps_client.search_one(
            query, location=location, max_results=results_per_query, seen_place_ids=seen_place_ids
        )
        print(f"    Apify returned {len(raw_leads)} results.", file=sys.stderr)

        enriched: list[PlaceLead] = []
        for lead in raw_leads:
            lead.coverage_market = market_name

            if lead.dedupe_key() in existing_keys:
                print(f"    skip (dup): {lead.business_name}", file=sys.stderr)
                continue
            if not qualifies_google_business(lead):
                print(f"    skip (low signal): {lead.business_name}", file=sys.stderr)
                continue

            try:
                if lead.website:
                    crawl = scraper.crawl(lead.website)
                    lead.website_text = str(crawl.get("text", ""))
                    lead.pages_scraped = int(crawl.get("pages_scraped", 0))
                    lead.raw_emails = merge_unique(lead.raw_emails, list(crawl.get("emails", [])))
                    lead.raw_phones = merge_unique(lead.raw_phones, list(crawl.get("phones", [])))
                    lead.enrichment_status = "website_crawled"

                if should_use_ai(lead):
                    extracted = extractor.extract(lead)
                    lead.merge_extracted(extracted)
                    lead.enrichment_status = "ai_enriched"

                if not should_store_lead(lead):
                    print(f"    skip (not target): {lead.business_name}", file=sys.stderr)
                    continue

                enriched.append(lead)
                existing_keys.add(lead.dedupe_key())
                print(f"    queued: {lead.business_name} [{lead.lead_segment}]", file=sys.stderr)

            except Exception as exc:
                if _is_timeout(exc) and has_target_signals(lead):
                    lead.enrichment_status = "partial_timeout"
                    enriched.append(lead)
                    existing_keys.add(lead.dedupe_key())
                    print(f"    partial (timeout): {lead.business_name}", file=sys.stderr)
                else:
                    print(f"    error: {lead.business_name}: {exc}", file=sys.stderr)

        if enriched:
            store.upsert_leads(enriched)
            total_written += len(enriched)
            print(f"    wrote {len(enriched)} leads to sheet.", file=sys.stderr)

    tracker.record_run(
        market=market_name,
        query_count=len(queries),
        requested_results=args.max_results,
        written_results=total_written,
        mode="upsert",
    )
    print(f"Done. Wrote {total_written} leads for '{market_name}'.", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Moss supplier lead automation — Canada landscaping companies via Apify + Google Sheets."
    )
    parser.add_argument(
        "--market",
        choices=available_markets(),
        required=True,
        help="Target city/market to run.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=200,
        help="Max Apify results per run (split across queries). Default: 200.",
    )
    parser.add_argument("--force", action="store_true", help="Re-run even if market is already marked complete.")
    parser.add_argument("--spreadsheet-id", help="Override spreadsheet ID from .env.")
    parser.add_argument("--sheet-name", help="Override sheet name from .env.")
    return parser.parse_args()


def load_markets() -> dict:
    return json.loads(MARKETS_PATH.read_text())["markets"]


def available_markets() -> list[str]:
    try:
        return sorted(load_markets().keys())
    except Exception:
        return []


def load_market(name: str) -> dict:
    markets = load_markets()
    if name not in markets:
        raise ValueError(f"Unknown market: {name}. Available: {sorted(markets.keys())}")
    return markets[name]


def should_use_ai(lead: PlaceLead) -> bool:
    if not lead.website:
        return False
    if lead.primary_email() and lead.owner_or_contact:
        return False
    return True


def should_store_lead(lead: PlaceLead) -> bool:
    combined = " ".join(filter(None, [
        lead.business_name,
        lead.website_text[:6000],
        lead.address,
        lead.website,
        " ".join(lead.source_notes),
    ])).lower()

    has_positive = any(kw in combined for kw in POSITIVE_KEYWORDS)
    has_only_negative = any(kw in combined for kw in NEGATIVE_KEYWORDS) and not has_positive

    if has_only_negative:
        return False
    if lead.lead_segment in TARGET_SEGMENTS:
        return True
    return has_positive


def has_target_signals(lead: PlaceLead) -> bool:
    combined = " ".join(filter(None, [
        lead.business_name,
        lead.address,
        lead.website,
    ])).lower()
    if lead.lead_segment in TARGET_SEGMENTS:
        return True
    return any(kw in combined for kw in POSITIVE_KEYWORDS)


def _is_timeout(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(m in msg for m in ("timed out", "timeout", "read operation timed out")):
        return True
    return isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError, URLError))
