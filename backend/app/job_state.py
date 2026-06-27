from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import LeadGenerationJob
from .schemas import GenerateLeadRequest

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


_JOBS: dict[str, GenerationJobState] = {}
_JOBS_LOCK = threading.RLock()


def create_generation_job(payload: GenerateLeadRequest) -> GenerationJobState:
    job = GenerationJobState(id=str(uuid.uuid4()))
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    _create_job_record(job.id, payload)
    job.emit(status="queued", stage="Queued", progress=0)
    return job


def get_job(job_id: str) -> GenerationJobState | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def release_job(job_id: str) -> None:
    with _JOBS_LOCK:
        _JOBS.pop(job_id, None)


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


def update_job_record(
    db: Session,
    job: GenerationJobState,
    status: str,
    campaign_id: str | None = None,
    error: str = "",
    finished: bool = False,
) -> None:
    record = db.get(LeadGenerationJob, job.id)
    if not record:
        logger.warning("Generation job record %s was not found during update", job.id)
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
        logger.exception("Failed to persist generation job snapshot for %s", job.id)


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
