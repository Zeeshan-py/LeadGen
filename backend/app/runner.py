from __future__ import annotations

import json
import logging
import queue
import socket
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from lead_automation.ai_extractor import LeadExtractor
from lead_automation.apify_maps import ApifyMapsClient
from lead_automation.apify_web import ApifyWebCrawler
from lead_automation.contact_discovery import ContactDiscovery
from lead_automation.main import qualifies_google_business
from lead_automation.models import PlaceLead, merge_unique
from lead_automation.sheets import SheetsLeadStore
from lead_automation.website_scraper import WebsiteScraper
from lead_automation.social_links import SOCIAL_NETWORKS, social_network_for_url
from lead_automation.validation import normalize_website

from .ai import GeminiLeadAI, OutreachDrafts, WebsiteAnalysis
from .config import Settings, get_settings
from .database import SessionLocal
from .google_sheets import build_sheets_store, validate_google_sheets
from .models import Analytics, Campaign, Lead, LeadGenerationJob, Outreach
from .schemas import GenerateLeadRequest
from .screenshots import capture_website_screenshot
from .settings_store import effective_settings


PIPELINE = [
    "Searching Google Maps",
    "Scraping Websites",
    "Finding Emails",
    "Finding Phone Numbers",
    "Analyzing Websites",
    "Generating AI Insights",
    "Creating Personalized Outreach",
    "Saving Leads",
]
logger = logging.getLogger(__name__)


class LeadSkippedNoContact(RuntimeError):
    pass


class OptionalSheetsStore:
    def __init__(self, store: SheetsLeadStore | None = None) -> None:
        self.store = store

    def existing_dedupe_keys(self) -> set[str]:
        if not self.store:
            return set()
        try:
            return self.store.existing_dedupe_keys()
        except Exception:
            logger.exception("Google Sheets dedupe lookup failed")
            return set()

    def upsert_leads(self, leads: list[PlaceLead]) -> None:
        if not self.store:
            return
        try:
            self.store.upsert_leads(leads)
        except Exception:
            logger.exception("Google Sheets lead sync failed")


@dataclass
class GenerationJobState:
    id: str
    status: str = "queued"
    stage: str = "Queued"
    progress: int = 0
    lead_counter: int = 0
    success_counter: int = 0
    failure_counter: int = 0
    campaign_id: str | None = None
    error: str = ""
    events: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "lead_counter": self.lead_counter,
            "success_counter": self.success_counter,
            "failure_counter": self.failure_counter,
            "campaign_id": self.campaign_id,
            "error": self.error,
            "pipeline": PIPELINE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def emit(self, **updates: Any) -> None:
        for key, value in updates.items():
            setattr(self, key, value)
        payload = self.snapshot()
        self.events.put(payload)
        _persist_job_snapshot(self)


JOBS: dict[str, GenerationJobState] = {}


def create_generation_job(payload: GenerateLeadRequest) -> GenerationJobState:
    job = GenerationJobState(id=str(uuid.uuid4()))
    JOBS[job.id] = job
    _create_job_record(job.id, payload)
    job.emit(status="queued", stage="Queued", progress=0)
    return job


def get_job(job_id: str) -> GenerationJobState | None:
    return JOBS.get(job_id)


def get_job_snapshot(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)
    if job:
        return job.snapshot()
    with SessionLocal() as db:
        record = db.get(LeadGenerationJob, job_id)
        return _snapshot_from_record(record) if record else None


def get_latest_job_snapshot() -> dict[str, Any] | None:
    with SessionLocal() as db:
        record = db.scalar(select(LeadGenerationJob).order_by(desc(LeadGenerationJob.created_at)).limit(1))
        return _snapshot_from_record(record) if record else None


def run_generation_job(job_id: str, payload: GenerateLeadRequest) -> None:
    job = JOBS[job_id]
    settings = get_settings()
    started = time.time()
    try:
        with SessionLocal() as db:
            settings = effective_settings(settings, db)
            settings.require_generation_credentials()
            google_status = validate_google_sheets(settings)
            campaign = _create_campaign(db, payload)
            job.campaign_id = campaign.id
            _update_job_record(db, job, status="running", campaign_id=campaign.id)
            job.emit(status="running", stage="Searching Google Maps", progress=4)

            raw_leads = _search_google_maps(settings, payload)
            job.emit(stage="Searching Google Maps", lead_counter=len(raw_leads), progress=14)

            existing_keys = set(db.scalars(select(Lead.dedupe_key)).all())
            sheets_store = OptionalSheetsStore()
            if google_status.get("status") == "ok":
                try:
                    sheets_store = OptionalSheetsStore(build_sheets_store(settings))
                except Exception:
                    logger.exception("Google Sheets initialization failed; continuing with database storage")
            else:
                _record_event(
                    db,
                    "integration_warning",
                    campaign_id=campaign.id,
                    metadata={"integration": "google_sheets", "message": google_status.get("message", "")},
                )
            existing_keys.update(sheets_store.existing_dedupe_keys())

            ai = GeminiLeadAI(settings.gemini_api_key, settings.gemini_model) if settings.gemini_api_key else None
            scraper = _build_scraper(settings)
            extractor = LeadExtractor(settings.anthropic_api_key) if settings.anthropic_api_key else None

            candidates = [lead for lead in raw_leads if qualifies_google_business(lead)]
            max_count = max(len(candidates), 1)
            for index, lead in enumerate(candidates, start=1):
                base_progress = 14 + int((index - 1) / max_count * 78)
                if lead.dedupe_key() in existing_keys:
                    _record_event(
                        db,
                        "lead_skipped_duplicate",
                        campaign_id=campaign.id,
                        metadata={"business_name": lead.business_name},
                    )
                    continue
                try:
                    _process_one_lead(
                        db=db,
                        job=job,
                        lead=lead,
                        payload=payload,
                        campaign=campaign,
                        scraper=scraper,
                        extractor=extractor,
                        ai=ai,
                        sheets_store=sheets_store,
                        settings=settings,
                        base_progress=base_progress,
                    )
                    existing_keys.add(lead.dedupe_key())
                    job.success_counter += 1
                except LeadSkippedNoContact as exc:
                    _record_event(
                        db,
                        "lead_skipped_no_contact",
                        campaign_id=campaign.id,
                        metadata={"business_name": lead.business_name, "reason": str(exc)},
                    )
                    db.commit()
                    job.emit(stage="Saving Leads", progress=min(92, base_progress + 8), error="")
                except Exception as exc:
                    job.failure_counter += 1
                    _record_event(
                        db,
                        "lead_failed",
                        campaign_id=campaign.id,
                        metadata={"business_name": lead.business_name, "error": str(exc)},
                    )
                    db.commit()
                    job.emit(
                        stage="Saving Leads",
                        progress=min(92, base_progress + 8),
                        error=_friendly_error(exc, lead.business_name),
                    )

            campaign.status = "completed"
            campaign.leads_generated = job.success_counter
            db.add(campaign)
            db.commit()
            job.emit(status="completed", stage="Complete", progress=100)
            _update_job_record(db, job, status="completed", finished=True)
            _record_event(
                db,
                "generation_completed",
                campaign_id=campaign.id,
                metadata={
                    "duration_seconds": round(time.time() - started, 2),
                    "success_counter": job.success_counter,
                    "failure_counter": job.failure_counter,
                },
            )
            db.commit()
    except Exception as exc:
        job.status = "failed"
        logger.exception("Generation job %s failed", job_id)
        job.error = _friendly_error(exc)
        job.emit(status="failed", stage="Failed", progress=job.progress, error=job.error)
        with SessionLocal() as db:
            _update_job_record(db, job, status="failed", error=job.error, finished=True)


def _create_job_record(job_id: str, payload: GenerateLeadRequest) -> None:
    with SessionLocal() as db:
        db.add(
            LeadGenerationJob(
                id=job_id,
                status="queued",
                city="",
                state="",
                continent=payload.continent,
                country=payload.country,
                business_type=payload.business_type,
                website_mode=payload.website_mode,
                max_leads=payload.max_leads,
            )
        )
        db.commit()


def _update_job_record(
    db: Session,
    job: GenerationJobState,
    status: str,
    campaign_id: str | None = None,
    error: str = "",
    finished: bool = False,
) -> None:
    record = db.get(LeadGenerationJob, job.id)
    if not record:
        return
    record.status = status
    record.campaign_id = campaign_id or job.campaign_id
    record.progress = job.progress
    record.lead_counter = job.lead_counter
    record.success_counter = job.success_counter
    record.failure_counter = job.failure_counter
    record.error = error
    if finished:
        record.finished_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()


def _persist_job_snapshot(job: GenerationJobState) -> None:
    try:
        with SessionLocal() as db:
            record = db.get(LeadGenerationJob, job.id)
            if not record:
                return
            record.status = job.status
            record.campaign_id = job.campaign_id
            record.progress = job.progress
            record.lead_counter = job.lead_counter
            record.success_counter = job.success_counter
            record.failure_counter = job.failure_counter
            record.error = job.error
            db.add(record)
            db.commit()
    except Exception:
        pass


def _snapshot_from_record(record: LeadGenerationJob) -> dict[str, Any]:
    return {
        "job_id": record.id,
        "status": record.status,
        "stage": _stage_from_progress(record.status, record.progress),
        "progress": record.progress,
        "lead_counter": record.lead_counter,
        "success_counter": record.success_counter,
        "failure_counter": record.failure_counter,
        "campaign_id": record.campaign_id,
        "error": record.error,
        "pipeline": PIPELINE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _stage_from_progress(status: str, progress: int) -> str:
    if status == "queued":
        return "Queued"
    if status == "completed":
        return "Complete"
    if status == "failed":
        return "Failed"
    thresholds = [
        (98, "Saving Leads"),
        (95, "Creating Personalized Outreach"),
        (94, "Generating AI Insights"),
        (93, "Analyzing Websites"),
        (92, "Finding Phone Numbers"),
        (91, "Finding Emails"),
        (14, "Searching Google Maps"),
        (0, "Searching Google Maps"),
    ]
    for minimum, stage in thresholds:
        if progress >= minimum:
            return stage
    return "Queued"


def _create_campaign(db: Session, payload: GenerateLeadRequest) -> Campaign:
    name = payload.campaign_name or f"{payload.country} {payload.business_type}"
    campaign = Campaign(
        name=name,
        city="",
        state="",
        continent=payload.continent,
        country=payload.country,
        business_type=payload.business_type,
        status="running",
        max_leads=payload.max_leads,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    _record_event(db, "campaign_started", campaign_id=campaign.id, metadata={"name": name})
    db.commit()
    return campaign


def _search_google_maps(settings: Settings, payload: GenerateLeadRequest) -> list[PlaceLead]:
    location = payload.country
    client = ApifyMapsClient(settings.apify_api_token, settings.apify_actor_id)
    return client.search_one(
        query=payload.business_type,
        location=location,
        max_results=payload.max_leads,
        seen_place_ids=set(),
        website_filter=payload.website_mode,
    )


def _build_scraper(settings: Settings) -> WebsiteScraper:
    js_fallback = ApifyWebCrawler(
        api_token=settings.apify_api_token,
        actor_id=settings.apify_web_actor_id,
    )
    return WebsiteScraper(
        timeout_seconds=settings.fetch_timeout_seconds,
        max_pages=settings.max_website_pages,
        js_fallback=js_fallback,
    )


def _process_one_lead(
    db: Session,
    job: GenerationJobState,
    lead: PlaceLead,
    payload: GenerateLeadRequest,
    campaign: Campaign,
    scraper: WebsiteScraper,
    extractor: LeadExtractor | None,
    ai: GeminiLeadAI | None,
    sheets_store: OptionalSheetsStore,
    settings: Settings,
    base_progress: int,
) -> None:
    lead.coverage_market = campaign.name
    lead.search_query = payload.business_type

    job.emit(stage="Scraping Websites", progress=min(90, base_progress + 2), lead_counter=job.lead_counter)
    crawl = {"text": "", "emails": [], "phones": [], "social_links": {}, "social_pages": [], "pages_scraped": 0}
    social_from_url = _social_candidates_from_url(lead.website)
    if lead.website:
        supplied_website = lead.website
        lead.website = normalize_website(lead.website)
        social_from_url = _merge_social_sources(social_from_url, _social_candidates_from_url(lead.website))
        if not lead.website:
            raise ValueError(f"Invalid website URL: {supplied_website}")
        crawl = scraper.crawl(lead.website)
        if not crawl.get("website_valid", True) and not social_from_url:
            raise ValueError("Website could not be reached or validated")
        lead.website_text = str(crawl.get("text", ""))
        lead.pages_scraped = int(crawl.get("pages_scraped", 0))
        lead.raw_emails = merge_unique(lead.raw_emails, list(crawl.get("emails", [])))
        lead.enrichment_status = "website_crawled"

    job.emit(stage="Finding Emails", progress=min(91, base_progress + 4))
    job.emit(stage="Finding Phone Numbers", progress=min(92, base_progress + 5))
    lead.raw_phones = merge_unique(lead.raw_phones, list(crawl.get("phones", [])))
    social_candidates = _merge_social_sources(lead.social_links, social_from_url)
    _extend_social_candidates(social_candidates, crawl.get("social_links", {}))

    if settings.enable_contact_discovery and (not lead.primary_email() or not social_candidates):
        discovery_crawl = _discover_missing_contact_data(
            lead=lead,
            payload=payload,
            scraper=scraper,
            social_candidates=social_candidates,
            settings=settings,
        )
        if discovery_crawl:
            crawl = _merge_crawl_results(crawl, discovery_crawl)

    if social_candidates:
        lead.social_links = _normalize_social_links(social_candidates, ai)
    else:
        lead.social_links = {}
    lead.social_status = "found" if lead.social_links else "missing"

    if extractor and lead.website:
        extracted = extractor.extract(lead)
        lead.merge_extracted(extracted)
        if lead.enrichment_status == "website_crawled":
            lead.enrichment_status = "ai_enriched"

    if not _has_direct_contact(lead):
        raise LeadSkippedNoContact("No public email or social profile was found")

    job.emit(stage="Analyzing Websites", progress=min(93, base_progress + 6))
    analysis = _analyze_with_fallback(ai, lead, payload.business_type, crawl)

    job.emit(stage="Generating AI Insights", progress=min(94, base_progress + 7))
    outreach = _outreach_with_fallback(ai, lead, payload.business_type, analysis)

    screenshot_url = ""
    if settings.enable_screenshot_capture and lead.website:
        try:
            screenshot_url = capture_website_screenshot(
                lead.website,
                settings.screenshots_dir,
                settings.public_backend_url,
            )
        except Exception:
            screenshot_url = ""

    job.emit(stage="Creating Personalized Outreach", progress=min(95, base_progress + 8))
    db_lead = _upsert_lead(
        db,
        lead,
        payload,
        campaign,
        analysis,
        screenshot_url,
        social_pages=list(crawl.get("social_pages", [])),
    )
    _upsert_outreach(db, db_lead, campaign, outreach)
    sheets_store.upsert_leads([lead])
    _record_event(
        db,
        "lead_saved",
        lead_id=db_lead.id,
        campaign_id=campaign.id,
        metadata={"business_name": db_lead.business_name, "opportunity_score": db_lead.opportunity_score},
    )
    db.commit()
    job.emit(stage="Saving Leads", progress=min(98, base_progress + 10))


def _upsert_lead(
    db: Session,
    lead: PlaceLead,
    payload: GenerateLeadRequest,
    campaign: Campaign,
    analysis: WebsiteAnalysis,
    screenshot_url: str,
    social_pages: list[str],
) -> Lead:
    existing = db.scalar(select(Lead).where(Lead.dedupe_key == lead.dedupe_key()))
    row = existing or Lead(dedupe_key=lead.dedupe_key(), business_name=lead.business_name)
    row.campaign_id = campaign.id
    row.business_name = lead.business_name
    row.website = lead.website
    row.google_maps_url = lead.google_maps_url
    row.email = lead.primary_email()
    row.phone = lead.primary_phone()
    row.location = lead.address
    row.city = lead.city
    row.state = lead.state
    row.country = payload.country
    row.business_type = payload.business_type
    row.website_score = analysis.website_score
    row.opportunity_score = analysis.opportunity_score
    row.website_problems = analysis.website_problems
    row.website_summary = analysis.website_summary
    row.improvement_suggestions = analysis.improvement_suggestions
    row.lead_status = "qualified"
    row.outreach_status = row.outreach_status or "not_started"
    existing_tags = list(row.tags or [])
    row.tags = list(dict.fromkeys([payload.business_type, payload.country, *existing_tags]))
    row.social_links = dict(lead.social_links)
    row.social_status = lead.social_status
    row.screenshot_url = screenshot_url
    row.raw = {
        "place_id": lead.place_id,
        "rating": lead.rating,
        "user_rating_count": lead.user_rating_count,
        "lead_segment": lead.lead_segment,
        "pages_scraped": lead.pages_scraped,
        "social_pages": social_pages,
        "source_notes": lead.source_notes,
    }
    db.add(row)
    db.flush()
    return row


def _upsert_outreach(db: Session, lead: Lead, campaign: Campaign, drafts: OutreachDrafts) -> Outreach:
    existing = db.scalar(select(Outreach).where(Outreach.lead_id == lead.id))
    row = existing or Outreach(lead_id=lead.id, campaign_id=campaign.id, tracking_id=uuid.uuid4().hex)
    row.campaign_id = campaign.id
    row.subject_line = drafts.subject_line
    row.personalized_first_line = drafts.personalized_first_line
    row.cold_email = drafts.cold_email
    row.follow_up_1 = drafts.follow_up_1
    row.follow_up_2 = drafts.follow_up_2
    row.status = row.status if row.status != "draft" else "draft"
    db.add(row)
    return row


def _record_event(
    db: Session,
    event_type: str,
    lead_id: str | None = None,
    campaign_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        Analytics(
            event_type=event_type,
            lead_id=lead_id,
            campaign_id=campaign_id,
            metadata_json=metadata or {},
        )
    )


def is_timeout(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(m in msg for m in ("timed out", "timeout", "read operation timed out")):
        return True
    return isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError, URLError))


def _normalize_social_links(
    candidates: dict[str, list[str]], ai: GeminiLeadAI | None
) -> dict[str, str]:
    if ai:
        try:
            return ai.normalize_social_links(candidates)
        except Exception:
            logger.exception("AI social normalization failed; using deterministic normalization")
    result: dict[str, str] = {}
    for network in SOCIAL_NETWORKS:
        for value in candidates.get(network, []):
            if social_network_for_url(value) == network:
                result[network] = value
                break
    return result


def _merge_social_sources(
    existing: dict[str, str] | None,
    scraped: Any,
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    if existing:
        for network, link in existing.items():
            if network in SOCIAL_NETWORKS and link:
                merged.setdefault(network, []).append(link)
    if isinstance(scraped, dict):
        for network, links in scraped.items():
            if network not in SOCIAL_NETWORKS:
                continue
            values = links if isinstance(links, list) else [links]
            bucket = merged.setdefault(network, [])
            for link in values:
                value = str(link).strip()
                if value and value not in bucket:
                    bucket.append(value)
    return merged


def _extend_social_candidates(target: dict[str, list[str]], source: Any) -> None:
    if not isinstance(source, dict):
        return
    for network, links in source.items():
        if network not in SOCIAL_NETWORKS:
            continue
        values = links if isinstance(links, list) else [links]
        bucket = target.setdefault(network, [])
        for link in values:
            value = str(link).strip()
            if value and value not in bucket:
                bucket.append(value)


def _social_candidates_from_url(url: str) -> dict[str, list[str]]:
    network = social_network_for_url(url)
    if not network:
        return {}
    return {network: [url]}


def _has_direct_contact(lead: PlaceLead) -> bool:
    return bool(lead.primary_email() or lead.social_links)


def _discover_missing_contact_data(
    lead: PlaceLead,
    payload: GenerateLeadRequest,
    scraper: WebsiteScraper,
    social_candidates: dict[str, list[str]],
    settings: Settings,
) -> dict[str, Any]:
    discovery = ContactDiscovery(
        timeout_seconds=min(settings.fetch_timeout_seconds, 12),
        max_results=settings.contact_discovery_results,
    )
    location = ", ".join(part for part in (lead.address, payload.country) if part)
    result = discovery.search_business(lead.business_name, location, payload.business_type)
    if not (result.emails or result.social_links or result.website_candidates):
        return {}

    lead.raw_emails = merge_unique(lead.raw_emails, result.emails)
    _extend_social_candidates(social_candidates, result.social_links)
    lead.source_notes = merge_unique(
        lead.source_notes,
        [f"Contact discovery checked {url}" for url in result.source_urls[:3]],
    )

    for candidate in result.website_candidates[:2]:
        if lead.website and candidate == lead.website:
            continue
        candidate_crawl = scraper.crawl(candidate)
        if not candidate_crawl.get("website_valid", True):
            continue
        lead.raw_emails = merge_unique(lead.raw_emails, list(candidate_crawl.get("emails", [])))
        lead.raw_phones = merge_unique(lead.raw_phones, list(candidate_crawl.get("phones", [])))
        _extend_social_candidates(social_candidates, candidate_crawl.get("social_links", {}))
        if not lead.website:
            lead.website = candidate
        if not lead.website_text:
            lead.website_text = str(candidate_crawl.get("text", ""))
        lead.pages_scraped += int(candidate_crawl.get("pages_scraped", 0))
        if lead.enrichment_status == "google_only":
            lead.enrichment_status = "contact_discovered"
        return candidate_crawl

    if lead.enrichment_status == "google_only":
        lead.enrichment_status = "contact_discovered"
    return {}


def _merge_crawl_results(primary: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    merged["text"] = "\n\n".join(filter(None, [str(primary.get("text", "")), str(extra.get("text", ""))]))[:40_000]
    merged["emails"] = merge_unique(list(primary.get("emails", [])), list(extra.get("emails", [])))
    merged["phones"] = merge_unique(list(primary.get("phones", [])), list(extra.get("phones", [])))
    merged["pages_scraped"] = int(primary.get("pages_scraped", 0)) + int(extra.get("pages_scraped", 0))
    merged["social_pages"] = merge_unique(list(primary.get("social_pages", [])), list(extra.get("social_pages", [])))
    merged["social_links"] = _merge_social_sources(primary.get("social_links", {}), extra.get("social_links", {}))
    merged["website_valid"] = bool(primary.get("website_valid", True) or extra.get("website_valid", True))
    return merged


def _analyze_with_fallback(
    ai: GeminiLeadAI | None, lead: PlaceLead, business_type: str, crawl: dict[str, Any]
) -> WebsiteAnalysis:
    if ai:
        try:
            return ai.analyze_website(lead, business_type, crawl)
        except Exception:
            logger.exception("AI website analysis failed for %s", lead.business_name)
    has_website = bool(lead.website and crawl.get("website_valid", True))
    return WebsiteAnalysis(
        website_score=50 if has_website else 0,
        opportunity_score=50 if has_website else 80,
        website_problems=[] if has_website else ["No valid website found"],
        website_summary="Website was crawled; AI analysis was unavailable." if has_website else "No valid website was available.",
        improvement_suggestions=[],
    )


def _outreach_with_fallback(
    ai: GeminiLeadAI | None, lead: PlaceLead, business_type: str, analysis: WebsiteAnalysis
) -> OutreachDrafts:
    if ai:
        try:
            return ai.generate_outreach(lead, business_type, analysis)
        except Exception:
            logger.exception("AI outreach generation failed for %s", lead.business_name)
    return OutreachDrafts("", "", "", "", "")


def _friendly_error(exc: Exception, business_name: str = "") -> str:
    text = str(exc)
    prefix = f"{business_name}: " if business_name else ""
    lowered = text.lower()
    if "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
        return f"{prefix}AI quota is temporarily unavailable; non-AI enrichment will continue."
    if is_timeout(exc):
        return f"{prefix}The external service timed out."
    return f"{prefix}{text[:300]}"
