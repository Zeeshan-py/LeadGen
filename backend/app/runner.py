"""Lead generation job orchestration.

The runner owns the background execution path for discovery, enrichment,
analysis, persistence, and progress snapshots. It currently uses in-process
state and should be moved behind an external queue before horizontal scaling.
"""

from __future__ import annotations

import logging
import socket
import ssl
import time
from urllib.error import URLError

from sqlalchemy import select
from sqlalchemy.orm import Session

from lead_automation.ai_extractor import LeadExtractor
from lead_automation.apify_web import ApifyWebCrawler
from lead_automation.models import PlaceLead
from lead_automation.sheets import SheetsLeadStore
from lead_automation.website_scraper import WebsiteScraper

from .ai import GeminiLeadAI
from .config import Settings, get_settings
from .database import SessionLocal
from .google_sheets import build_sheets_store
from .job_state import (
    PIPELINE,
    GenerationJobState,
    create_generation_job,
    get_job,
    get_job_snapshot,
    get_latest_job_snapshot,
    release_job,
    update_job_record,
)
from .models import Campaign, Lead
from .schemas import GenerateLeadRequest
from .services.events import record_event
from .services.lead_pipeline import LeadPipeline
from .services.lead_search import (
    LeadSearchService,
    LeadSkippedNoContact,
    LeadValidationService,
)
from .settings_store import effective_settings

logger = logging.getLogger(__name__)

__all__ = [
    "PIPELINE",
    "GenerationJobState",
    "create_generation_job",
    "get_job",
    "get_job_snapshot",
    "get_latest_job_snapshot",
    "run_generation_job",
]


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
        if not self.store or not leads:
            return
        try:
            self.store.upsert_leads(leads)
        except Exception:
            logger.exception("Google Sheets lead sync failed")


def run_generation_job(job_id: str, payload: GenerateLeadRequest, user_id: str) -> None:
    job = get_job(job_id)
    if not job:
        logger.error("Generation job %s is not available in memory", job_id)
        return

    settings = get_settings()
    started = time.monotonic()
    logger.info(
        "Generation job %s started for %s in %s (city=%s, limit=%s, website_mode=%s)",
        job_id,
        payload.business_type,
        payload.country,
        payload.city or "all",
        payload.max_leads,
        payload.website_mode,
    )
    try:
        with SessionLocal() as db:
            settings = effective_settings(settings, db, user_id)
            settings.require_generation_credentials()
            campaign = _create_campaign(db, payload, user_id)
            job.campaign_id = campaign.id
            update_job_record(db, job, status="running", campaign_id=campaign.id)
            job.emit(status="running", stage="Searching Google Maps", progress=4)

            raw_leads = LeadSearchService(settings).search(payload)
            job.emit(
                stage="Searching Google Maps",
                lead_counter=len(raw_leads),
                progress=14,
            )

            sheets_store = _build_optional_sheets_store(settings, db, campaign.id)
            existing_keys = set(
                db.scalars(select(Lead.dedupe_key).where(Lead.user_id == user_id)).all()
            )
            existing_keys.update(sheets_store.existing_dedupe_keys())

            validation = LeadValidationService()
            candidates = validation.eligible_candidates(raw_leads)
            pipeline = _build_pipeline(db, settings, validation, user_id)
            leads_for_sheets: list[PlaceLead] = []
            max_count = max(len(candidates), 1)

            logger.info(
                "Generation job %s found %s raw leads and %s eligible leads",
                job_id,
                len(raw_leads),
                len(candidates),
            )
            for index, lead in enumerate(candidates, start=1):
                base_progress = 14 + int((index - 1) / max_count * 78)
                if lead.dedupe_key() in existing_keys:
                    record_event(
                        db,
                        "lead_skipped_duplicate",
                        campaign_id=campaign.id,
                        metadata={"business_name": lead.business_name},
                    )
                    logger.info("Skipped duplicate lead %s", lead.business_name)
                    continue
                try:
                    pipeline.process(
                        lead=lead,
                        payload=payload,
                        campaign=campaign,
                        base_progress=base_progress,
                        report_progress=lambda stage, progress: job.emit(
                            stage=stage,
                            progress=progress,
                        ),
                    )
                    existing_keys.add(lead.dedupe_key())
                    leads_for_sheets.append(lead)
                    job.success_counter += 1
                    logger.info("Saved enriched lead %s", lead.business_name)
                except LeadSkippedNoContact as exc:
                    record_event(
                        db,
                        "lead_skipped_no_contact",
                        campaign_id=campaign.id,
                        metadata={
                            "business_name": lead.business_name,
                            "reason": str(exc),
                        },
                    )
                    db.commit()
                    job.emit(
                        stage="Saving Leads",
                        progress=min(92, base_progress + 8),
                        error="",
                    )
                    logger.info("Skipped uncontactable lead %s: %s", lead.business_name, exc)
                except Exception as exc:
                    job.failure_counter += 1
                    record_event(
                        db,
                        "lead_failed",
                        campaign_id=campaign.id,
                        metadata={
                            "business_name": lead.business_name,
                            "error": str(exc),
                        },
                    )
                    db.commit()
                    job.emit(
                        stage="Saving Leads",
                        progress=min(92, base_progress + 8),
                        error=_friendly_error(exc, lead.business_name),
                    )
                    logger.exception("Lead processing failed for %s", lead.business_name)

            sheets_store.upsert_leads(leads_for_sheets)
            campaign.status = "completed"
            campaign.leads_generated = job.success_counter
            db.add(campaign)
            db.commit()
            job.emit(status="completed", stage="Complete", progress=100)
            update_job_record(db, job, status="completed", finished=True)
            duration = round(time.monotonic() - started, 2)
            record_event(
                db,
                "generation_completed",
                campaign_id=campaign.id,
                metadata={
                    "duration_seconds": duration,
                    "success_counter": job.success_counter,
                    "failure_counter": job.failure_counter,
                },
            )
            db.commit()
            logger.info(
                "Generation job %s completed in %.2fs (%s saved, %s failed)",
                job_id,
                duration,
                job.success_counter,
                job.failure_counter,
            )
    except Exception as exc:
        logger.exception("Generation job %s failed", job_id)
        job.error = _friendly_error(exc)
        job.emit(
            status="failed",
            stage="Failed",
            progress=job.progress,
            error=job.error,
        )
        with SessionLocal() as db:
            if job.campaign_id:
                campaign = db.get(Campaign, job.campaign_id)
                if campaign and campaign.status == "running":
                    campaign.status = "failed"
                    db.add(campaign)
            update_job_record(
                db,
                job,
                status="failed",
                error=job.error,
                finished=True,
            )
    finally:
        release_job(job_id)


def _build_pipeline(
    db: Session,
    settings: Settings,
    validation: LeadValidationService,
    user_id: str,
) -> LeadPipeline:
    js_fallback = ApifyWebCrawler(
        api_token=settings.apify_api_token,
        actor_id=settings.apify_web_actor_id,
    )
    scraper = WebsiteScraper(
        timeout_seconds=settings.fetch_timeout_seconds,
        max_pages=settings.max_website_pages,
        js_fallback=js_fallback,
    )
    ai = (
        GeminiLeadAI(settings.gemini_api_key, settings.gemini_model)
        if settings.gemini_api_key
        else None
    )
    contact_extractor = (
        LeadExtractor(settings.anthropic_api_key)
        if settings.anthropic_api_key
        else None
    )
    return LeadPipeline(
        db=db,
        settings=settings,
        scraper=scraper,
        ai=ai,
        contact_extractor=contact_extractor,
        validation=validation,
        user_id=user_id,
    )


def _build_optional_sheets_store(
    settings: Settings,
    db: Session,
    campaign_id: str,
) -> OptionalSheetsStore:
    if not settings.google_sheets_spreadsheet_id.strip():
        record_event(
            db,
            "integration_warning",
            campaign_id=campaign_id,
            metadata={
                "integration": "google_sheets",
                "message": (
                    "Google Sheets spreadsheet ID is missing. "
                    "Set GOOGLE_SHEETS_SPREADSHEET_ID."
                ),
            },
        )
        return OptionalSheetsStore()
    try:
        return OptionalSheetsStore(build_sheets_store(settings))
    except Exception as exc:
        logger.exception(
            "Google Sheets initialization failed; continuing with database storage"
        )
        record_event(
            db,
            "integration_warning",
            campaign_id=campaign_id,
            metadata={
                "integration": "google_sheets",
                "message": str(exc),
            },
        )
        return OptionalSheetsStore()


def _create_campaign(db: Session, payload: GenerateLeadRequest, user_id: str) -> Campaign:
    market = ", ".join(part for part in (payload.city, payload.country) if part)
    name = payload.campaign_name or f"{market} {payload.business_type}"
    campaign = Campaign(
        user_id=user_id,
        name=name,
        city=payload.city,
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
    record_event(
        db,
        "campaign_started",
        campaign_id=campaign.id,
        metadata={"name": name},
    )
    db.commit()
    return campaign


def is_timeout(exc: Exception) -> bool:
    message = str(exc).lower()
    if any(marker in message for marker in ("timed out", "timeout", "read operation timed out")):
        return True
    if isinstance(exc, URLError):
        reason = str(getattr(exc, "reason", "")).lower()
        return any(marker in reason for marker in ("timed out", "timeout"))
    return isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError))


def _friendly_error(exc: Exception, business_name: str = "") -> str:
    text = str(exc)
    prefix = f"{business_name}: " if business_name else ""
    lowered = text.lower()
    if "http error 402" in lowered or "payment required" in lowered:
        return (
            f"{prefix}Apify could not start the Google Maps search because the account requires payment "
            "or has no available credits."
        )
    if "http error 401" in lowered or "unauthorized" in lowered:
        return f"{prefix}Apify rejected the API token. Check APIFY_API_TOKEN."
    if "http error 403" in lowered or "forbidden" in lowered:
        return f"{prefix}Apify denied access to the Google Maps actor or account."
    if "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
        return f"{prefix}AI quota is temporarily unavailable; non-AI enrichment will continue."
    if is_timeout(exc):
        if "apify" in lowered or "google maps" in lowered:
            return (
                f"{prefix}Apify Google Maps search timed out. "
                "Please retry with fewer leads or try again in a few minutes."
            )
        return f"{prefix}The external service timed out."
    return f"{prefix}{text[:300]}"
