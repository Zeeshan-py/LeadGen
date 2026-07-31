"""LeadForge FastAPI application entrypoint.

This module wires the platform routers, production authentication middleware,
health checks, lead generation orchestration, outreach, analytics, settings,
and static frontend serving. Route handlers here are intentionally thin around
shared services, but the file remains the operational center of the deployed
backend process.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import StringIO
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session, joinedload

from ai_sdr.api.router import router as ai_sdr_router
from ai_sdr.config import get_ai_sdr_settings
from .ai import GeminiLeadAI, WebsiteAnalysis
from .auth import CSRF_COOKIE, authenticate_request, get_current_user
from .auth_routes import router as auth_router
from .config import get_settings
from .crm import router as crm_router
from .database import SessionLocal, check_db, get_db
from .disposable_email import load_disposable_email_domains
from .email_sync import sync_replied_outreach
from .gmail import GmailConfigurationError, GmailSendError
from .gmail_connections import GmailConnectionRequiredError, get_connected_gmail_connection, gmail_client_for_user
from .gmail_routes import router as gmail_router
from .google_sheets import validate_google_sheets
from .models import Analytics, Campaign, EmailMessage, Lead, LeadGenerationJob, Outreach, Setting, User
from .paddle_routes import router as paddle_router
from .runner import create_generation_job, get_job, get_job_snapshot, get_latest_job_snapshot, run_generation_job
from .schemas import (
    AnalyticsResponse,
    CampaignCreate,
    CampaignRead,
    GenerateLeadRequest,
    JobCreated,
    LeadRead,
    LeadUpdate,
    OutreachRead,
    SendEmailRequest,
    SettingsPayload,
)
from .services.lead_analysis import LeadAnalysisService
from .services.crm import change_crm_stage, mark_contacted, record_crm_activity
from .settings_store import effective_settings
from .subscription_access import (
    assert_generate_leads_allowed,
    assert_lead_filters_allowed,
    assert_outreach_send_allowed,
    require_feature,
)
from .twilio_routes import router as twilio_router

settings = get_settings()
logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("lead_automation").setLevel(logging.INFO)
app = FastAPI(title="LeadForge AI API", version="1.0.0")
app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(twilio_router)
app.include_router(paddle_router)
app.include_router(crm_router)
app.include_router(ai_sdr_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.screenshots_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/screenshots", StaticFiles(directory=settings.screenshots_dir), name="screenshots")


PROTECTED_API_PREFIXES = (
    "/generate-leads",
    "/get-leads",
    "/get-campaigns",
    "/outreach",
    "/send-email",
    "/get-analytics",
    "/settings",
    "/gmail",
    "/twilio",
    "/billing",
    "/health/google",
    "/crm",
    "/ai-sdr",
)
PUBLIC_API_PREFIXES = (
    "/auth",
    "/email/open",
    "/static/screenshots",
    "/ai-sdr/calls/twilio",
    "/billing/plans",
    "/billing/webhook",
)
PUBLIC_API_EXACT_PATHS = {"/health", "/health/live", "/health/ready"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
BACKEND_DOCUMENT_PREFIXES = (
    "/auth",
    "/email/open",
    "/static/screenshots",
    "/gmail/connect",
    "/gmail/callback",
    "/ai-sdr/calls/twilio",
)
SEO_FILE_PATHS = {
    "/robots.txt",
    "/sitemap.xml",
    "/manifest.webmanifest",
    "/favicon.ico",
    "/brand/icon.svg",
    "/brand/icon-192.png",
    "/brand/icon-512.png",
    "/brand/leadforge-og.png",
    "/brand/leadforge-og.svg",
    "/brand/mask-icon.svg",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), clipboard-write=(self)",
    )
    response.headers.setdefault("X-DNS-Prefetch-Control", "on")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
    response.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=31536000; includeSubDomains; preload",
    )
    response.headers.setdefault("Content-Security-Policy", _content_security_policy())

    if path.startswith("/_next/static/") or _is_versioned_static_asset_path(path):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    elif path in {"/robots.txt", "/sitemap.xml", "/manifest.webmanifest", "/sitemap"}:
        response.headers.setdefault("Cache-Control", "public, max-age=300")
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers.setdefault("Cache-Control", "public, max-age=0, must-revalidate")

    return response


def _content_security_policy() -> str:
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.paddle.com https://*.paddle.com https://www.googletagmanager.com https://www.google-analytics.com https://ssl.google-analytics.com",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https://*.paddle.com https://www.googletagmanager.com https://www.google-analytics.com https://*.googleusercontent.com https://avatars.githubusercontent.com",
        "font-src 'self' data:",
        "connect-src 'self' https://*.paddle.com https://sandbox-api.paddle.com https://api.paddle.com https://www.googletagmanager.com https://www.google-analytics.com https://analytics.google.com https://stats.g.doubleclick.net https://region1.google-analytics.com",
        "frame-src https://*.paddle.com https://www.googletagmanager.com",
        "worker-src 'self' blob:",
        "manifest-src 'self'",
        "upgrade-insecure-requests",
    ]
    return "; ".join(directives)


@app.get("/sitemap", include_in_schema=False)
def sitemap_alias() -> RedirectResponse:
    return RedirectResponse(url="/sitemap.xml", status_code=308)


@app.middleware("http")
async def protect_api_routes(request: Request, call_next):
    path = request.url.path
    if _should_serve_frontend_document(request):
        response = _frontend_page_response(path.strip("/") or "index")
        if response:
            return response
    if request.method == "OPTIONS" or not _is_protected_api_path(path):
        return await call_next(request)
    if _is_public_api_path(path):
        return await call_next(request)
    with SessionLocal() as db:
        try:
            authenticate_request(request, db, settings)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    path = request.url.path
    if (
        request.method in UNSAFE_METHODS
        and _is_protected_api_path(path)
        and not _is_public_api_path(path)
        and not request.headers.get("authorization", "").lower().startswith("bearer ")
        and request.cookies.get("leadforge_access")
    ):
        header_token = request.headers.get("x-csrf-token", "")
        cookie_token = request.cookies.get(CSRF_COOKIE, "")
        if not header_token or not cookie_token or header_token != cookie_token:
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    return await call_next(request)


@app.on_event("startup")
async def on_startup() -> None:
    settings.validate_production()
    get_ai_sdr_settings().validate_calling_startup()
    await asyncio.to_thread(load_disposable_email_domains, settings)
    try:
        validate_google_sheets(settings)
    except Exception:
        logger.exception("Google Sheets startup validation failed")
    app.state.reply_sync_task = asyncio.create_task(_reply_sync_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    task = getattr(app.state, "reply_sync_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health/live")
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        check_db()
    except Exception as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ready", "database": "ok"}


@app.get("/health/google")
def google_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return validate_google_sheets(effective_settings(settings, db, current_user.id))


@app.post("/generate-leads", response_model=JobCreated)
def generate_leads(
    payload: GenerateLeadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobCreated:
    assert_generate_leads_allowed(
        db,
        current_user,
        requested_count=payload.max_leads,
        website_mode=payload.website_mode,
        campaign_name=payload.campaign_name,
    )
    job = create_generation_job(payload, current_user.id)
    background_tasks.add_task(run_generation_job, job.id, payload, current_user.id)
    return JobCreated(
        job_id=job.id,
        status=job.status,
        events_url=f"/generate-leads/{job.id}/events",
    )


@app.get("/generate-leads/latest")
def get_latest_generate_job(current_user: User = Depends(get_current_user)) -> dict[str, Any] | None:
    return get_latest_job_snapshot(current_user.id)


@app.get("/generate-leads/{job_id}")
def get_generate_job(job_id: str, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    snapshot = get_job_snapshot(job_id, current_user.id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return snapshot


@app.get("/generate-leads/{job_id}/events")
async def stream_generate_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    job = get_job(job_id)
    if job and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if not job:
        snapshot = get_job_snapshot(job_id, current_user.id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Generation job not found")

        async def record_event_stream():
            yield _sse(snapshot)

        return StreamingResponse(record_event_stream(), media_type="text/event-stream")

    async def event_stream():
        yield _sse(job.snapshot())
        while True:
            try:
                event = await asyncio.to_thread(job.events.get, True, 15)
                yield _sse(event)
                if event.get("status") in {"completed", "failed"}:
                    break
            except Exception:
                yield ": heartbeat\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/get-leads", response_model=list[LeadRead])
def get_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str = "",
    status: str = "",
    outreach_status: str = "",
    campaign_id: str = "",
    scope: str = Query(default="latest", pattern="^(latest|all)$"),
    country: str = "",
    business_type: str = "",
    contact: str = Query(default="", pattern="^(|email|phone|social)$"),
    sort: str = "-created_at",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Lead]:
    assert_lead_filters_allowed(
        db,
        current_user,
        campaign_id=campaign_id,
        outreach_status=outreach_status,
        contact=contact,
    )
    query = select(Lead).where(Lead.user_id == current_user.id)
    if scope == "latest" and not campaign_id:
        latest_job = db.scalar(
            select(LeadGenerationJob)
            .where(LeadGenerationJob.user_id == current_user.id)
            .where(LeadGenerationJob.campaign_id.is_not(None))
            .order_by(desc(LeadGenerationJob.created_at))
            .limit(1)
        )
        if latest_job and latest_job.campaign_id:
            query = query.where(Lead.campaign_id == latest_job.campaign_id)
        else:
            return []
    if search:
        like = f"%{search}%"
        query = query.where(
            Lead.business_name.ilike(like)
            | Lead.website.ilike(like)
            | Lead.email.ilike(like)
            | Lead.phone.ilike(like)
            | Lead.city.ilike(like)
            | Lead.business_type.ilike(like)
        )
    if status:
        query = query.where(Lead.lead_status == status)
    if outreach_status:
        query = query.where(Lead.outreach_status == outreach_status)
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
    if country:
        query = query.where(Lead.country == country)
    if business_type:
        query = query.where(Lead.business_type == business_type)
    if contact == "email":
        query = query.where(Lead.email != "")
    elif contact == "phone":
        query = query.where(Lead.phone != "")
    elif contact == "social":
        query = query.where(Lead.social_status == "found")

    column_name = sort.removeprefix("-")
    column = getattr(Lead, column_name, Lead.created_at)
    query = query.order_by(desc(column) if sort.startswith("-") else asc(column))
    return list(db.scalars(query.offset(offset).limit(limit)).all())


@app.patch("/get-leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Lead:
    require_feature(db, current_user, "crm")
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.add(lead)
    db.add(Analytics(user_id=current_user.id, event_type="lead_updated", lead_id=lead.id, campaign_id=lead.campaign_id))
    db.commit()
    db.refresh(lead)
    return lead


@app.get("/get-leads/export.csv")
def export_leads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: str = Query(default="latest", pattern="^(latest|all)$"),
    campaign_id: str = "",
) -> Response:
    require_feature(db, current_user, "csv_export")
    query = select(Lead).where(Lead.user_id == current_user.id).order_by(desc(Lead.created_at))
    if campaign_id:
        query = query.where(Lead.campaign_id == campaign_id)
    elif scope == "latest":
        latest_job = db.scalar(
            select(LeadGenerationJob)
            .where(LeadGenerationJob.user_id == current_user.id)
            .where(LeadGenerationJob.campaign_id.is_not(None))
            .order_by(desc(LeadGenerationJob.created_at))
            .limit(1)
        )
        if latest_job and latest_job.campaign_id:
            query = query.where(Lead.campaign_id == latest_job.campaign_id)
        else:
            return Response("", media_type="text/csv")
    leads = db.scalars(query).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Business Name",
            "Website",
            "Email",
            "Phone",
            "Country",
            "City",
            "Facebook",
            "Instagram",
            "LinkedIn",
            "YouTube",
            "X/Twitter",
            "TikTok",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                lead.business_name,
                lead.website,
                lead.email,
                lead.phone,
                lead.country,
                lead.city,
                (lead.social_links or {}).get("facebook", ""),
                (lead.social_links or {}).get("instagram", ""),
                (lead.social_links or {}).get("linkedin", ""),
                (lead.social_links or {}).get("youtube", ""),
                (lead.social_links or {}).get("x_twitter", ""),
                (lead.social_links or {}).get("tiktok", ""),
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leadforge-leads.csv"},
    )


@app.get("/get-campaigns", response_model=list[CampaignRead])
def get_campaigns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Campaign]:
    require_feature(db, current_user, "campaigns")
    return list(
        db.scalars(
            select(Campaign)
            .where(Campaign.user_id == current_user.id)
            .order_by(desc(Campaign.created_at))
        ).all()
    )


@app.post("/get-campaigns", response_model=CampaignRead)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Campaign:
    require_feature(db, current_user, "campaigns")
    campaign = Campaign(user_id=current_user.id, **payload.model_dump(), status="draft")
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@app.get("/outreach", response_model=list[OutreachRead])
def get_outreach(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    lead_id: str = "",
    status: str = "",
) -> list[Outreach]:
    require_feature(db, current_user, "outreach")
    query = select(Outreach).where(Outreach.user_id == current_user.id).order_by(desc(Outreach.created_at))
    if lead_id:
        query = query.where(Outreach.lead_id == lead_id)
    if status:
        query = query.where(Outreach.status == status)
    return list(db.scalars(query).all())


@app.post("/outreach/{lead_id}/regenerate", response_model=OutreachRead)
def regenerate_outreach(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Outreach:
    require_feature(db, current_user, "outreach")
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    try:
        effective = effective_settings(settings, db, current_user.id)
        ai = (
            GeminiLeadAI(effective.gemini_api_key, effective.gemini_model)
            if effective.gemini_api_key
            else None
        )
        analysis = WebsiteAnalysis(
            website_score=lead.website_score,
            opportunity_score=lead.opportunity_score,
            website_summary=lead.website_summary,
            website_problems=lead.website_problems,
            improvement_suggestions=lead.improvement_suggestions,
        )
        from lead_automation.models import PlaceLead

        place_lead = PlaceLead(
            business_name=lead.business_name,
            website=lead.website,
            address=lead.location,
            email=lead.email,
            phone=lead.phone,
        )
        drafts = LeadAnalysisService(
            ai=ai,
            contact_extractor=None,
        ).generate_outreach(place_lead, lead.business_type, analysis)
        outreach = db.scalar(
            select(Outreach).where(Outreach.user_id == current_user.id, Outreach.lead_id == lead.id)
        )
        if not outreach:
            outreach = Outreach(user_id=current_user.id, lead_id=lead.id, campaign_id=lead.campaign_id)
        outreach.subject_line = drafts.subject_line
        outreach.personalized_first_line = drafts.personalized_first_line
        outreach.cold_email = drafts.cold_email
        outreach.follow_up_1 = drafts.follow_up_1
        outreach.follow_up_2 = drafts.follow_up_2
        outreach.failed_reason = drafts.generation_error
        if lead.crm_stage not in {"won", "lost", "archived"}:
            change_crm_stage(db, lead, "email_generated", actor="LeadForge AI")
        record_crm_activity(
            db,
            lead_id=lead.id,
            event_type="email_generated",
            title="Email generated",
            description=outreach.subject_line,
            actor="LeadForge AI",
        )
        db.add(outreach)
        db.commit()
        db.refresh(outreach)
        return outreach
    except Exception as exc:
        logger.exception("Outreach regeneration failed for lead %s", lead_id)
        raise HTTPException(
            status_code=503,
            detail=(
                "Outreach generation failed after one retry. "
                "The existing draft was left unchanged."
            ),
        ) from exc


@app.post("/send-email", response_model=OutreachRead)
def send_email(
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Outreach:
    assert_outreach_send_allowed(db, current_user)
    outreach = db.scalar(
        select(Outreach).options(joinedload(Outreach.lead), joinedload(Outreach.campaign)).where(
            Outreach.id == payload.outreach_id,
            Outreach.user_id == current_user.id,
        )
    )
    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")
    try:
        effective = effective_settings(settings, db, current_user.id)
        if not outreach.lead or not outreach.lead.email.strip():
            raise RuntimeError("This lead does not have a valid email address.")
        body = str(getattr(outreach, payload.version) or "").strip()
        if not body:
            raise RuntimeError(
                "The selected outreach draft is empty. Regenerate it before sending."
            )
        subject = outreach.subject_line.strip()
        if not subject:
            raise RuntimeError(
                "The outreach subject line is empty. Regenerate it before sending."
            )
        gmail = gmail_client_for_user(db, effective, current_user.id)
        tracking_url = f"{effective.public_backend_url.rstrip('/')}/email/open/{outreach.tracking_id}.png"
        sent = gmail.send_email(
            outreach.lead.email,
            subject,
            body,
            tracking_url,
        )
        outreach.status = "sent"
        outreach.selected_version = payload.version
        outreach.gmail_message_id = sent.message_id
        outreach.gmail_thread_id = sent.thread_id
        outreach.sent_at = datetime.now(timezone.utc)
        outreach.lead.outreach_status = "sent"
        mark_contacted(outreach.lead, outreach.sent_at)
        if outreach.lead.crm_stage not in {"won", "lost", "archived"}:
            change_crm_stage(db, outreach.lead, "email_sent", actor="LeadForge AI")
        event_type = "follow_up_sent" if payload.version.startswith("follow_up") else "email_sent"
        event_title = "Follow-up sent" if event_type == "follow_up_sent" else "Email sent"
        db.add(
            EmailMessage(
                user_id=current_user.id,
                lead_id=outreach.lead_id,
                outreach_id=outreach.id,
                gmail_message_id=sent.message_id,
                gmail_thread_id=sent.thread_id,
                direction="sent",
                from_email=gmail.sender_email,
                to_email=outreach.lead.email,
                subject=subject,
                body_text=body,
                snippet=body[:240],
                message_at=outreach.sent_at,
            )
        )
        record_crm_activity(
            db,
            lead_id=outreach.lead_id,
            event_type=event_type,
            title=event_title,
            description=subject,
            actor="LeadForge user",
            metadata={
                "gmail_message_id": sent.message_id,
                "gmail_thread_id": sent.thread_id,
                "version": payload.version,
            },
        )
        if outreach.campaign:
            outreach.campaign.emails_sent += 1
        db.add(Analytics(user_id=current_user.id, event_type="email_sent", lead_id=outreach.lead_id, campaign_id=outreach.campaign_id))
        db.commit()
        db.refresh(outreach)
        return outreach
    except GmailConnectionRequiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GmailConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Email send failed for outreach %s", payload.outreach_id)
        outreach.status = "failed"
        outreach.failed_reason = str(exc)
        outreach.lead.outreach_status = "failed"
        db.commit()
        if isinstance(exc, (GmailConfigurationError, GmailSendError)):
            detail = str(exc)
        elif isinstance(exc, RuntimeError):
            detail = str(exc)
        else:
            detail = (
                "Email sending failed unexpectedly. Check the backend logs for details."
            )
        raise HTTPException(status_code=400, detail=detail) from exc


@app.post("/send-email/sync-statuses")
def sync_email_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int | bool]:
    require_feature(db, current_user, "reply_sync")
    return sync_replied_outreach(db, settings, user_id=current_user.id).to_dict()


@app.get("/email/open/{tracking_id}.png")
def track_open(tracking_id: str, db: Session = Depends(get_db)) -> Response:
    outreach = db.scalar(select(Outreach).options(joinedload(Outreach.lead)).where(Outreach.tracking_id == tracking_id))
    if outreach and outreach.status in {"sent", "opened"}:
        outreach.status = "opened"
        outreach.opened_at = datetime.now(timezone.utc)
        outreach.lead.outreach_status = "opened"
        if outreach.lead.crm_stage not in {"replied", "interested", "meeting_scheduled", "won", "lost", "archived"}:
            change_crm_stage(db, outreach.lead, "opened", actor="Gmail tracking")
        record_crm_activity(
            db,
            lead_id=outreach.lead_id,
            event_type="email_opened",
            title="Email opened",
            actor="Gmail tracking",
            metadata={"tracking_id": tracking_id},
        )
        db.add(Analytics(user_id=outreach.user_id, event_type="email_opened", lead_id=outreach.lead_id, campaign_id=outreach.campaign_id))
        db.commit()
    pixel = base64_pixel()
    return Response(pixel, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/get-analytics", response_model=AnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsResponse:
    require_feature(db, current_user, "analytics")
    leads = db.scalars(select(Lead).where(Lead.user_id == current_user.id)).all()
    outreach = db.scalars(select(Outreach).where(Outreach.user_id == current_user.id)).all()
    events = db.scalars(
        select(Analytics)
        .where(Analytics.user_id == current_user.id)
        .order_by(desc(Analytics.created_at))
        .limit(50)
    ).all()

    emails_sent = sum(1 for item in outreach if item.sent_at or item.status in {"sent", "opened", "replied", "closed"})
    replies = sum(1 for item in outreach if item.status == "replied" or item.replied_at)
    opens = sum(1 for item in outreach if item.status in {"opened", "replied"} or item.opened_at)
    open_rate = round((opens / emails_sent) * 100, 1) if emails_sent else 0.0
    opportunities = sum(1 for lead in leads if lead.opportunity_score >= 70)
    conversion_rate = round((replies / emails_sent) * 100, 1) if emails_sent else 0.0
    latest_job = db.scalar(
        select(LeadGenerationJob)
        .where(LeadGenerationJob.user_id == current_user.id)
        .order_by(desc(LeadGenerationJob.created_at))
        .limit(1)
    )
    latest_leads = [lead for lead in leads if latest_job and lead.campaign_id == latest_job.campaign_id]
    social_links_found = sum(len(lead.social_links or {}) for lead in latest_leads)

    leads_by_day: defaultdict[str, int] = defaultdict(int)
    emails_by_day: defaultdict[str, int] = defaultdict(int)
    for lead in leads:
        leads_by_day[lead.created_at.date().isoformat()] += 1
    for item in outreach:
        if item.sent_at:
            emails_by_day[item.sent_at.date().isoformat()] += 1

    top_cities = Counter(lead.city for lead in leads if lead.city).most_common(8)
    top_niches = Counter(lead.business_type for lead in leads if lead.business_type).most_common(8)

    return AnalyticsResponse(
        leads_found=latest_job.lead_counter if latest_job else 0,
        leads_saved=latest_job.success_counter if latest_job else 0,
        emails_found=sum(1 for lead in latest_leads if lead.email),
        social_links_found=social_links_found,
        failed_leads=latest_job.failure_counter if latest_job else 0,
        total_leads_generated=len(leads),
        emails_sent=emails_sent,
        replies_received=replies,
        open_rate=open_rate,
        website_opportunities_found=opportunities,
        conversion_rate=conversion_rate,
        lead_generation_per_day=[{"date": k, "leads": v} for k, v in sorted(leads_by_day.items())],
        emails_per_day=[{"date": k, "emails": v} for k, v in sorted(emails_by_day.items())],
        top_cities=[{"city": k, "count": v} for k, v in top_cities],
        top_niches=[{"niche": k, "count": v} for k, v in top_niches],
        recent_activity=[
            {
                "id": event.id,
                "type": event.event_type,
                "metadata": event.metadata_json,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    )


@app.get("/settings", response_model=None)
def get_settings_rows(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if _wants_frontend_document(request):
        response = _frontend_page_response("settings")
        if response:
            return response

    rows = db.scalars(select(Setting).where(Setting.user_id == current_user.id)).all()
    payload = {row.key: ("********" if row.is_secret else row.value) for row in rows}
    gmail_connection = get_connected_gmail_connection(db, current_user.id)
    payload.update(
        {
            "default_lead_limit": settings.default_lead_limit,
            "google_sheets_id_configured": bool(settings.google_sheets_spreadsheet_id),
            "apify_configured": bool(settings.apify_api_token),
            "gemini_configured": bool(settings.gemini_api_key),
            "gmail_configured": bool(settings.gmail_client_id and settings.gmail_client_secret),
            "gmail_connected": bool(gmail_connection),
        }
    )
    return payload


@app.put("/settings")
def update_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    secret_map = {
        "gemini_api_key": payload.gemini_api_key,
        "apify_api_key": payload.apify_api_key,
    }
    regular_map = {
        "google_sheets_id": payload.google_sheets_id,
        "default_lead_limit": payload.default_lead_limit,
        "export_settings": payload.export_settings,
    }
    for key, value in secret_map.items():
        if value is not None:
            db.merge(Setting(user_id=current_user.id, key=key, value={"value": value}, is_secret=True))
    for key, value in regular_map.items():
        if value is not None:
            db.merge(Setting(user_id=current_user.id, key=key, value={"value": value}, is_secret=False))
    db.commit()
    return {"status": "saved"}


async def _reply_sync_loop() -> None:
    await asyncio.sleep(5)
    while True:
        try:
            await asyncio.to_thread(_sync_replies_once)
        except Exception:
            logger.exception("Automatic Gmail reply sync failed")
        await asyncio.sleep(max(15, settings.gmail_reply_sync_interval_seconds))


def _sync_replies_once() -> None:
    with SessionLocal() as db:
        for user in db.scalars(select(User)).all():
            try:
                require_feature(db, user, "reply_sync")
            except HTTPException as exc:
                if exc.status_code == 403:
                    continue
                raise
            sync_replied_outreach(
                db,
                settings,
                raise_on_missing_credentials=False,
                user_id=user.id,
            )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _is_protected_api_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PROTECTED_API_PREFIXES)


def _is_public_api_path(path: str) -> bool:
    return path in PUBLIC_API_EXACT_PATHS or any(
        path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_API_PREFIXES
    )


def _wants_frontend_document(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    sec_fetch_dest = request.headers.get("sec-fetch-dest", "").lower()
    return sec_fetch_dest == "document" or ("text/html" in accept and "application/json" not in accept)


def _should_serve_frontend_document(request: Request) -> bool:
    path = request.url.path
    return (
        request.method == "GET"
        and _wants_frontend_document(request)
        and not _is_backend_document_path(path)
        and not _is_frontend_static_asset_path(path)
    )


def _is_backend_document_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in BACKEND_DOCUMENT_PREFIXES)


def _is_frontend_static_asset_path(path: str) -> bool:
    leaf = path.rsplit("/", 1)[-1]
    return path == "/sitemap" or path in SEO_FILE_PATHS or "." in leaf


def _is_versioned_static_asset_path(path: str) -> bool:
    return path.startswith("/brand/") or path.endswith((".css", ".js", ".woff2", ".png", ".svg", ".ico"))


def _frontend_page_response(page: str) -> FileResponse | None:
    static_dir = settings.frontend_static_dir
    page_file = static_dir / page.strip("/") / "index.html"
    if page_file.is_file():
        return FileResponse(page_file)
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return None


def base64_pixel() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )


if settings.frontend_static_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=settings.frontend_static_dir, html=True),
        name="frontend",
    )
