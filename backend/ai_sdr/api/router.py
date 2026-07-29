"""HTTP API boundary for the independent AI SDR module."""

from __future__ import annotations

import csv
import json
from io import StringIO
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_sdr.calling import default_calling_orchestrator
from ai_sdr.config import get_ai_sdr_settings
from ai_sdr.conversation import ConversationState, default_conversation_manager
from ai_sdr.schemas import (
    AISDRBatchRead,
    AISDRBulkActionResult,
    AISDRBulkContactAction,
    AISDRCallControl,
    AISDRCallSessionRead,
    AISDRCallStart,
    AISDRCallTranscriptCreate,
    AISDRContactInput,
    AISDRConversationResponse,
    AISDRConversationStart,
    AISDRConversationTurn,
    AISDRContactSummary,
    AISDRCustomCallResponse,
    AISDRCustomCallTarget,
    AISDRDashboardResponse,
    AISDRImportCreate,
    AISDRImportDetail,
    AISDRImportResponse,
    AISDRImportStatus,
    AISDRManualContactCreate,
    AISDRManualBridgeCallResponse,
    AISDRManualBridgeCallStart,
    AISDRRestContactsCreate,
    AISDRSourceDescriptor,
    AISDRSourceType,
)
from ai_sdr.services.dashboard import AISDRDashboardService
from ai_sdr.services.ingestion import AISDRIngestionService
from ai_sdr.services.sources import supported_sources
from app.auth import get_current_user
from app.database import get_db
from app.models import Lead, User

settings = get_ai_sdr_settings()
router = APIRouter(prefix=settings.api_prefix, tags=["ai-sdr"])


@router.get("/health")
def ai_sdr_health() -> dict[str, str | bool]:
    return {"status": "ok", "module": "ai_sdr", "enabled": settings.enabled}


@router.get("/sources", response_model=list[AISDRSourceDescriptor])
def get_sources() -> list[AISDRSourceDescriptor]:
    return supported_sources()


@router.get("/conversation/states", response_model=list[str])
def get_conversation_states() -> list[str]:
    return [state.value for state in ConversationState]


@router.post("/calls/outbound", response_model=AISDRCallSessionRead)
async def start_outbound_call(
    payload: AISDRCallStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        _require_user_contact(db, payload.contact_id, current_user.id)
        session = await default_calling_orchestrator.start_outbound_call(
            db,
            contact_id=payload.contact_id,
            objective=payload.objective,
            actor=payload.actor,
            user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/calls/manual-bridge", response_model=AISDRManualBridgeCallResponse)
async def start_manual_bridge_call(
    payload: AISDRManualBridgeCallStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        if payload.contact_id:
            _require_user_contact(db, payload.contact_id, current_user.id)
        return await default_calling_orchestrator.start_manual_bridge_call(
            db,
            contact_id=payload.contact_id,
            to_number=payload.to_phone,
            business_name=payload.business_name,
            owner_number=payload.owner_phone,
            actor=payload.actor,
            user_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/calls/custom-target", response_model=AISDRCustomCallResponse)
async def start_custom_target_call(
    payload: AISDRCustomCallTarget,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    actor = payload.actor.strip() or settings.default_actor
    objective = _custom_target_objective(payload)
    contact_notes = "\n\n".join(
        part
        for part in (
            payload.notes.strip(),
            f"Specific offer: {payload.offer.strip()}",
            f"AI SDR instructions: {payload.instructions.strip()}",
            f"Instagram: {payload.instagram_url.strip()}" if payload.instagram_url.strip() else "",
        )
        if part
    )
    try:
        imported = AISDRIngestionService(db, current_user.id).ingest_contacts(
            AISDRImportCreate(
                source_type=AISDRSourceType.MANUAL_ENTRY,
                contacts=[
                    AISDRContactInput(
                        business_name=payload.business_name,
                        contact_name=payload.owner_name,
                        phone=payload.phone,
                        email=payload.email,
                        website=payload.website,
                        industry=payload.industry,
                        city=payload.city,
                        notes=contact_notes,
                        tags=["AI SDR", "Custom Call", "Manual Offer"],
                        raw={
                            "instagram_url": payload.instagram_url,
                            "custom_offer": payload.offer,
                            "custom_instructions": payload.instructions,
                            "source": "custom_target_call",
                        },
                    )
                ],
                configuration={
                    "entrypoint": "ai_sdr_custom_call_target",
                    "instagram_url": payload.instagram_url,
                    "offer": payload.offer,
                    "instructions": payload.instructions,
                },
                created_by=actor,
            )
        )
        lead_id = next((record.crm_lead_id for record in imported.records if record.crm_lead_id), None)
        if not lead_id:
            raise ValueError("Custom call target could not be stored in CRM.")
        session = await default_calling_orchestrator.start_outbound_call(
            db,
            contact_id=lead_id,
            objective=objective,
            actor=actor,
            user_id=current_user.id,
        )
        contact = AISDRDashboardService(db, current_user.id).get_contact(lead_id)
        if not contact:
            raise LookupError("AI SDR contact was stored but could not be loaded.")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"contact": contact.model_dump(), "call": session.to_dict()}


@router.get("/calls", response_model=list[AISDRCallSessionRead])
def list_calls(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return [
        session.to_dict()
        for session in default_calling_orchestrator.list_sessions()
        if _contact_belongs_to_user(db, session.contact_id, current_user.id)
    ]


@router.get("/calls/{call_id}", response_model=AISDRCallSessionRead)
def get_call(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = default_calling_orchestrator.get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="AI SDR call session not found")
    _require_user_contact(db, session.contact_id, current_user.id)
    return session.to_dict()


@router.post("/calls/{call_id}/control", response_model=AISDRCallSessionRead)
async def control_call(
    call_id: str,
    payload: AISDRCallControl,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        session = default_calling_orchestrator.get_session(call_id)
        if not session:
            raise LookupError("AI SDR call session not found")
        _require_user_contact(db, session.contact_id, current_user.id)
        session = await default_calling_orchestrator.control_call(
            db,
            call_id=call_id,
            action=payload.action,
            actor=payload.actor,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/calls/{call_id}/transcript", response_model=AISDRCallSessionRead)
async def inject_call_transcript(
    call_id: str,
    payload: AISDRCallTranscriptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        session = default_calling_orchestrator.get_session(call_id)
        if not session:
            raise LookupError("AI SDR call session not found")
        _require_user_contact(db, session.contact_id, current_user.id)
        session = await default_calling_orchestrator.inject_transcript(
            db,
            call_id=call_id,
            role=payload.role,
            text=payload.text,
            actor=payload.actor,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session.to_dict()


@router.post("/calls/{call_id}/complete", response_model=AISDRCallSessionRead)
async def complete_call(
    call_id: str,
    payload: AISDRCallControl | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        session = default_calling_orchestrator.get_session(call_id)
        if not session:
            raise LookupError("AI SDR call session not found")
        _require_user_contact(db, session.contact_id, current_user.id)
        session = await default_calling_orchestrator.complete_call(
            db,
            call_id=call_id,
            actor=payload.actor if payload else settings.default_actor,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session.to_dict()


@router.api_route("/calls/twilio/voice", methods=["GET", "POST"])
async def twilio_voice_response(call_id: str, request: Request) -> Response:
    body = await request.body()
    _validate_twilio_request(request, body, call_id=call_id)
    try:
        twiml = default_calling_orchestrator.build_voice_response(call_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(twiml, media_type="application/xml")


@router.post("/calls/twilio/status")
async def twilio_status_callback(
    call_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    body = await request.body()
    _validate_twilio_request(request, body, call_id=call_id)
    payload = _request_payload(request, body)
    session = await default_calling_orchestrator.handle_status_update(
        db,
        call_id=call_id,
        payload=payload,
        actor=settings.default_actor,
    )
    if not session:
        raise HTTPException(status_code=404, detail="AI SDR call session not found")
    return {"status": "ok"}


@router.api_route("/calls/twilio/manual-bridge", methods=["GET", "POST"])
async def twilio_manual_bridge_response(call_id: str, request: Request) -> Response:
    body = await request.body()
    _validate_twilio_request(request, body, call_id=call_id)
    try:
        twiml = default_calling_orchestrator.build_manual_bridge_response(call_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(twiml, media_type="application/xml")


@router.post("/calls/twilio/manual-bridge/status")
async def twilio_manual_bridge_status(call_id: str, request: Request) -> dict[str, str]:
    body = await request.body()
    _validate_twilio_request(request, body, call_id=call_id)
    payload = _request_payload(request, body)
    default_calling_orchestrator.handle_manual_bridge_status(call_id, payload)
    return {"status": "ok"}


@router.websocket("/calls/twilio/media")
async def twilio_media_stream(websocket: WebSocket) -> None:
    await default_calling_orchestrator.handle_twilio_media_stream(websocket)


@router.post("/conversations", response_model=AISDRConversationResponse)
def start_conversation(
    payload: AISDRConversationStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if payload.contact_id:
        _require_user_contact(db, payload.contact_id, current_user.id)
        response = default_conversation_manager.start_for_contact(db, payload.contact_id)
        if not response:
            raise HTTPException(status_code=404, detail="AI SDR contact not found")
        return response
    if not payload.company:
        raise HTTPException(status_code=400, detail="Conversation requires contact_id or company context")
    return default_conversation_manager.start_from_context(
        company_payload=payload.company,
        owner_payload=payload.owner,
    )


@router.get("/conversations/{session_id}", response_model=AISDRConversationResponse)
def get_conversation(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    response = default_conversation_manager.get_session(session_id)
    if not response:
        raise HTTPException(status_code=404, detail="AI SDR conversation session not found")
    if response.get("contact_id"):
        _require_user_contact(db, str(response["contact_id"]), current_user.id)
    return response


@router.post("/conversations/{session_id}/turn", response_model=AISDRConversationResponse)
def add_conversation_turn(
    session_id: str,
    payload: AISDRConversationTurn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    existing = default_conversation_manager.get_session(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="AI SDR conversation session not found")
    if existing.get("contact_id"):
        _require_user_contact(db, str(existing["contact_id"]), current_user.id)
    response = default_conversation_manager.receive_customer_message(session_id, payload.message)
    if not response:
        raise HTTPException(status_code=404, detail="AI SDR conversation session not found")
    return response


@router.get("/dashboard", response_model=AISDRDashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str = "",
    industry: str = "",
    city: str = "",
    source: str = "",
    search: str = "",
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AISDRDashboardResponse:
    return AISDRDashboardService(db, current_user.id).dashboard(
        status=status,
        industry=industry,
        city=city,
        source=source,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/contacts/{contact_id}", response_model=AISDRContactSummary)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRContactSummary:
    contact = AISDRDashboardService(db, current_user.id).get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="AI SDR contact not found")
    return contact


@router.post("/contacts/bulk-delete", response_model=AISDRBulkActionResult)
def bulk_delete_contacts(
    payload: AISDRBulkContactAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRBulkActionResult:
    return AISDRDashboardService(db, current_user.id).archive_contacts(
        payload.contact_ids,
        actor=payload.actor.strip() or settings.default_actor,
    )


@router.post("/contacts/export.csv")
def export_contacts(
    payload: AISDRBulkContactAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    dashboard = AISDRDashboardService(db, current_user.id).dashboard(limit=500)
    selected_ids = set(payload.contact_ids) if payload else set()
    contacts = [
        contact
        for contact in dashboard.contacts
        if not selected_ids or contact.id in selected_ids
    ]
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Company",
            "Contact",
            "Phone",
            "Email",
            "Industry",
            "Status",
            "Source",
            "Pipeline Stage",
            "Next Follow-up",
            "City",
            "Country",
        ]
    )
    for contact in contacts:
        writer.writerow(
            [
                contact.company,
                contact.contact,
                contact.phone,
                contact.email,
                contact.industry,
                contact.status,
                contact.source,
                contact.pipeline_stage,
                contact.next_follow_up.isoformat() if contact.next_follow_up else "",
                contact.city,
                contact.country,
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leadforge-ai-sdr-contacts.csv"},
    )


@router.post("/imports", response_model=AISDRImportResponse)
def create_import(
    payload: AISDRImportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRImportResponse:
    return _ingest(payload, db, current_user)


@router.get("/imports", response_model=list[AISDRBatchRead])
def list_imports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    source_type: AISDRSourceType | None = None,
    status: AISDRImportStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AISDRBatchRead]:
    return AISDRIngestionService(db, current_user.id).list_batches(
        source_type=source_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/imports/{batch_id}", response_model=AISDRImportDetail)
def get_import(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRImportDetail:
    batch = AISDRIngestionService(db, current_user.id).get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="AI SDR import batch not found")
    return batch


@router.post("/contacts/manual", response_model=AISDRImportResponse)
def create_manual_contact(
    payload: AISDRManualContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRImportResponse:
    return _ingest(
        AISDRImportCreate(
            source_type=AISDRSourceType.MANUAL_ENTRY,
            contacts=[payload.contact],
            configuration=payload.configuration,
            created_by=payload.created_by,
        ),
        db,
        current_user,
    )


@router.post("/contacts", response_model=AISDRImportResponse)
def create_rest_contacts(
    payload: AISDRRestContactsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISDRImportResponse:
    return _ingest(
        AISDRImportCreate(
            source_type=AISDRSourceType.REST_API,
            contacts=payload.contacts,
            configuration=payload.configuration,
            created_by=payload.created_by,
        ),
        db,
        current_user,
    )


def _ingest(payload: AISDRImportCreate, db: Session, current_user: User) -> AISDRImportResponse:
    try:
        return AISDRIngestionService(db, current_user.id).ingest_contacts(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _contact_belongs_to_user(db: Session, contact_id: str, user_id: str) -> bool:
    if not contact_id:
        return False
    return bool(
        db.scalar(
            select(Lead.id)
            .where(Lead.id == contact_id, Lead.user_id == user_id)
            .limit(1)
        )
    )


def _require_user_contact(db: Session, contact_id: str, user_id: str) -> Lead:
    lead = db.scalar(
        select(Lead)
        .where(Lead.id == contact_id, Lead.user_id == user_id)
        .limit(1)
    )
    if not lead:
        raise HTTPException(status_code=404, detail="AI SDR contact not found")
    return lead


def _custom_target_objective(payload: AISDRCustomCallTarget) -> str:
    context = [
        f"Business: {payload.business_name.strip()}",
        f"Owner/contact: {payload.owner_name.strip() or 'unknown'}",
        f"Industry: {payload.industry.strip() or 'unknown'}",
        f"City: {payload.city.strip() or 'unknown'}",
        f"Website: {payload.website.strip() or 'not provided'}",
        f"Instagram: {payload.instagram_url.strip() or 'not provided'}",
        f"Specific offer: {payload.offer.strip()}",
        f"User instructions: {payload.instructions.strip()}",
    ]
    if payload.notes.strip():
        context.append(f"Additional notes: {payload.notes.strip()}")
    context.append(
        "Call behavior: open naturally, mention only relevant context, follow the user instructions exactly, "
        "qualify interest, handle objections calmly, and ask for the best next step."
    )
    return "\n".join(context)


def _request_payload(request: Request, body: bytes) -> dict[str, str]:
    content_type = request.headers.get("content-type", "")
    text = body.decode("utf-8") if body else ""
    if "application/json" in content_type and text:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return {str(key): str(value) for key, value in value.items()} if isinstance(value, dict) else {}
    return {key: value for key, value in parse_qsl(text, keep_blank_values=True)}


def _validate_twilio_request(request: Request, body: bytes, *, call_id: str = "") -> None:
    if not settings.twilio_validate_signature:
        return
    auth_token = ""
    if call_id:
        try:
            auth_token = default_calling_orchestrator.twilio_auth_token_for_call(call_id)
        except LookupError:
            auth_token = ""
    if not auth_token:
        raise HTTPException(status_code=503, detail="Twilio call credentials are not available")
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Twilio signature")
    try:
        from twilio.request_validator import RequestValidator
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Twilio package is not installed") from exc
    validator = RequestValidator(auth_token)
    payload = _request_payload(request, body)
    if not validator.validate(str(request.url), payload, signature):
        raise HTTPException(status_code=401, detail="Invalid Twilio signature")
