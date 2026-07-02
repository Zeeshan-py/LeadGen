from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import get_settings
from .database import get_db
from .email_sync import sync_replied_outreach
from .models import (
    CrmUser,
    EmailMessage,
    Lead,
    LeadActivity,
    LeadNote,
    LeadTag,
    Outreach,
)
from .schemas import (
    CrmActivityRead,
    CrmEmailMessageRead,
    CrmLeadDetail,
    CrmLeadListResponse,
    CrmLeadSummary,
    CrmLeadUpdate,
    CrmNoteCreate,
    CrmNoteRead,
    CrmTagRead,
    CrmTagsUpdate,
    CrmUserCreate,
    CrmUserRead,
    OutreachRead,
)
from .services.crm import (
    CRM_STAGES,
    change_crm_stage,
    record_crm_activity,
    replace_lead_tags,
)

router = APIRouter(prefix="/crm", tags=["crm"])
settings = get_settings()

LEAD_LOAD_OPTIONS = (
    selectinload(Lead.assigned_user),
    selectinload(Lead.crm_tag_links).selectinload(LeadTag.tag),
)

LEAD_DETAIL_OPTIONS = (
    *LEAD_LOAD_OPTIONS,
    selectinload(Lead.outreach_items),
    selectinload(Lead.email_messages),
    selectinload(Lead.crm_notes),
    selectinload(Lead.crm_activities),
)


@router.get("/users", response_model=list[CrmUserRead])
def get_crm_users(db: Session = Depends(get_db)) -> list[CrmUser]:
    return list(
        db.scalars(
            select(CrmUser)
            .where(CrmUser.is_active.is_(True))
            .order_by(CrmUser.name)
        ).all()
    )


@router.post("/users", response_model=CrmUserRead)
def create_crm_user(payload: CrmUserCreate, db: Session = Depends(get_db)) -> CrmUser:
    email = payload.email.strip().lower()
    if email and db.scalar(select(CrmUser).where(CrmUser.email == email)):
        raise HTTPException(status_code=409, detail="A CRM user with this email already exists")
    initials = payload.initials.strip().upper() or _initials(payload.name)
    user = CrmUser(
        name=payload.name.strip(),
        email=email,
        initials=initials,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/leads", response_model=CrmLeadListResponse)
def get_crm_leads(
    db: Session = Depends(get_db),
    search: str = "",
    stage: str = "",
    country: str = "",
    industry: str = "",
    assigned_user_id: str = "",
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    last_contacted_from: datetime | None = None,
    last_contacted_to: datetime | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CrmLeadListResponse:
    if stage and stage not in CRM_STAGES:
        raise HTTPException(status_code=400, detail="Unsupported CRM stage")
    filters = _lead_filters(
        search=search,
        country=country,
        industry=industry,
        assigned_user_id=assigned_user_id,
        created_from=created_from,
        created_to=created_to,
        last_contacted_from=last_contacted_from,
        last_contacted_to=last_contacted_to,
    )
    count_rows = db.execute(
        select(Lead.crm_stage, func.count(Lead.id))
        .where(*filters)
        .group_by(Lead.crm_stage)
    ).all()
    stage_counts = {stage_name: 0 for stage_name in CRM_STAGES}
    stage_counts.update({str(stage_name): int(count) for stage_name, count in count_rows})

    item_filters = [*filters]
    if stage:
        item_filters.append(Lead.crm_stage == stage)
    total = int(
        db.scalar(select(func.count(Lead.id)).where(*item_filters)) or 0
    )
    rows = db.scalars(
        select(Lead)
        .options(*LEAD_LOAD_OPTIONS)
        .where(*item_filters)
        .order_by(Lead.next_follow_up_at.asc().nulls_last(), Lead.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return CrmLeadListResponse(
        items=[_lead_summary(row) for row in rows],
        total=total,
        stage_counts=stage_counts,
    )


@router.get("/leads/{lead_id}", response_model=CrmLeadDetail)
def get_crm_lead(lead_id: str, db: Session = Depends(get_db)) -> CrmLeadDetail:
    return _lead_detail(_get_lead(db, lead_id))


@router.patch("/leads/{lead_id}", response_model=CrmLeadDetail)
def update_crm_lead(
    lead_id: str,
    payload: CrmLeadUpdate,
    db: Session = Depends(get_db),
) -> CrmLeadDetail:
    lead = _get_lead(db, lead_id)
    changes = payload.model_dump(exclude_unset=True)
    stage = changes.pop("crm_stage", None)
    address = changes.pop("address", None)
    industry = changes.pop("industry", None)
    assigned_user_id = changes.get("assigned_user_id", lead.assigned_user_id)
    if assigned_user_id and not db.get(CrmUser, assigned_user_id):
        raise HTTPException(status_code=400, detail="Assigned CRM user does not exist")

    changed_fields: list[str] = []
    for key, value in changes.items():
        if getattr(lead, key) != value:
            setattr(lead, key, value)
            changed_fields.append(key)
    if address is not None and lead.location != address:
        lead.location = address
        changed_fields.append("address")
    if industry is not None and lead.business_type != industry:
        lead.business_type = industry
        changed_fields.append("industry")
    if stage:
        try:
            change_crm_stage(db, lead, stage)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "next_follow_up_at" in changed_fields:
        record_crm_activity(
            db,
            lead_id=lead.id,
            event_type="follow_up_scheduled",
            title="Follow-up scheduled",
            description=(
                lead.next_follow_up_at.isoformat()
                if lead.next_follow_up_at
                else "Follow-up cleared"
            ),
            actor="LeadForge user",
        )
    other_fields = [field for field in changed_fields if field != "next_follow_up_at"]
    if other_fields:
        record_crm_activity(
            db,
            lead_id=lead.id,
            event_type="lead_updated",
            title="Lead profile updated",
            description=", ".join(other_fields),
            actor="LeadForge user",
            metadata={"fields": other_fields},
        )
    db.commit()
    return _lead_detail(_get_lead(db, lead_id))


@router.post("/leads/{lead_id}/notes", response_model=CrmLeadDetail)
def add_crm_note(
    lead_id: str,
    payload: CrmNoteCreate,
    db: Session = Depends(get_db),
) -> CrmLeadDetail:
    lead = _get_lead(db, lead_id)
    note = LeadNote(
        lead_id=lead.id,
        body=payload.body.strip(),
        created_by=payload.created_by.strip() or "LeadForge user",
    )
    lead.notes = note.body
    db.add(note)
    record_crm_activity(
        db,
        lead_id=lead.id,
        event_type="note_added",
        title="Note added",
        description=note.body[:240],
        actor=note.created_by,
    )
    db.commit()
    return _lead_detail(_get_lead(db, lead_id))


@router.put("/leads/{lead_id}/tags", response_model=CrmLeadDetail)
def update_crm_tags(
    lead_id: str,
    payload: CrmTagsUpdate,
    db: Session = Depends(get_db),
) -> CrmLeadDetail:
    lead = _get_lead(db, lead_id)
    replace_lead_tags(db, lead, payload.tags)
    db.commit()
    return _lead_detail(_get_lead(db, lead_id))


@router.post("/leads/{lead_id}/sync-gmail", response_model=CrmLeadDetail)
def sync_crm_gmail_thread(
    lead_id: str,
    db: Session = Depends(get_db),
) -> CrmLeadDetail:
    _get_lead(db, lead_id)
    sync_replied_outreach(db, settings, lead_id=lead_id)
    return _lead_detail(_get_lead(db, lead_id))


def _lead_filters(
    *,
    search: str,
    country: str,
    industry: str,
    assigned_user_id: str,
    created_from: datetime | None,
    created_to: datetime | None,
    last_contacted_from: datetime | None,
    last_contacted_to: datetime | None,
) -> list[Any]:
    filters: list[Any] = []
    if search.strip():
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                Lead.business_name.ilike(like),
                Lead.contact_name.ilike(like),
                Lead.email.ilike(like),
                Lead.phone.ilike(like),
            )
        )
    if country:
        filters.append(Lead.country == country)
    if industry:
        filters.append(Lead.business_type == industry)
    if assigned_user_id == "unassigned":
        filters.append(Lead.assigned_user_id.is_(None))
    elif assigned_user_id:
        filters.append(Lead.assigned_user_id == assigned_user_id)
    if created_from:
        filters.append(Lead.created_at >= created_from)
    if created_to:
        filters.append(Lead.created_at <= created_to)
    if last_contacted_from:
        filters.append(Lead.last_contacted_at >= last_contacted_from)
    if last_contacted_to:
        filters.append(Lead.last_contacted_at <= last_contacted_to)
    return filters


def _get_lead(db: Session, lead_id: str) -> Lead:
    lead = db.scalar(
        select(Lead)
        .options(*LEAD_DETAIL_OPTIONS)
        .where(Lead.id == lead_id)
        .execution_options(populate_existing=True)
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


def _lead_summary(lead: Lead) -> CrmLeadSummary:
    tags = sorted([
        CrmTagRead.model_validate(link.tag)
        for link in lead.crm_tag_links
        if link.tag is not None
    ], key=lambda tag: tag.name.lower())
    if not tags:
        tags = [
            CrmTagRead(id=f"legacy:{name}", name=name, color="")
            for name in (lead.tags or [])
        ]
    return CrmLeadSummary(
        id=lead.id,
        campaign_id=lead.campaign_id,
        business_name=lead.business_name,
        contact_name=lead.contact_name,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        address=lead.location,
        city=lead.city,
        state=lead.state,
        country=lead.country,
        industry=lead.business_type,
        notes=lead.notes,
        crm_stage=lead.crm_stage,
        last_contacted_at=lead.last_contacted_at,
        next_follow_up_at=lead.next_follow_up_at,
        assigned_user=(
            CrmUserRead.model_validate(lead.assigned_user)
            if lead.assigned_user
            else None
        ),
        tags=tags,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _lead_detail(lead: Lead) -> CrmLeadDetail:
    summary = _lead_summary(lead)
    outreach_history = [
        OutreachRead.model_validate(row)
        for row in sorted(
            lead.outreach_items,
            key=lambda row: row.created_at,
            reverse=True,
        )
    ]
    email_messages = [
        CrmEmailMessageRead.model_validate(row)
        for row in sorted(lead.email_messages, key=lambda row: row.message_at)
    ]
    note_history = [
        CrmNoteRead.model_validate(row)
        for row in sorted(
            lead.crm_notes,
            key=lambda row: row.created_at,
            reverse=True,
        )
    ]
    activity = [
        _activity_read(row)
        for row in sorted(
            lead.crm_activities,
            key=lambda row: row.created_at,
            reverse=True,
        )
    ]
    return CrmLeadDetail(
        **summary.model_dump(),
        outreach_history=outreach_history,
        email_messages=email_messages,
        note_history=note_history,
        activity=activity,
    )


def _activity_read(row: LeadActivity) -> CrmActivityRead:
    return CrmActivityRead(
        id=row.id,
        event_type=row.event_type,
        title=row.title,
        description=row.description,
        actor=row.actor,
        metadata=row.metadata_json,
        created_at=row.created_at,
    )


def _initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "LF"
