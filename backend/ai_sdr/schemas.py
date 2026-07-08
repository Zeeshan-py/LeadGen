"""Pydantic contracts for AI SDR APIs, imports, dashboard data, and conversations."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AISDRSourceType(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    GOOGLE_SHEETS = "google_sheets"
    MANUAL_ENTRY = "manual_entry"
    REST_API = "rest_api"
    CRM = "crm"
    FUTURE_INTEGRATION = "future_integration"


class AISDRImportStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class AISDRRecordStatus(str, Enum):
    RECEIVED = "received"
    NORMALIZED = "normalized"
    STORED = "stored"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class AISDRSourceDescriptor(BaseModel):
    type: AISDRSourceType
    label: str
    status: str
    entrypoint: str
    notes: str


class AISDRContactInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    company_name: str | None = Field(default=None, max_length=240)
    business_name: str | None = Field(default=None, max_length=240)
    contact_name: str | None = Field(default=None, max_length=180)
    first_name: str | None = Field(default=None, max_length=90)
    last_name: str | None = Field(default=None, max_length=90)
    title: str | None = Field(default=None, max_length=180)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    external_id: str | None = Field(default=None, max_length=255)
    raw: dict[str, Any] = Field(default_factory=dict)


class AISDRImportCreate(BaseModel):
    source_type: AISDRSourceType
    contacts: list[AISDRContactInput] = Field(min_length=1, max_length=10_000)
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="LeadForge AI SDR", max_length=160)


class AISDRManualContactCreate(BaseModel):
    contact: AISDRContactInput
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="LeadForge user", max_length=160)


class AISDRRestContactsCreate(BaseModel):
    contacts: list[AISDRContactInput] = Field(min_length=1, max_length=10_000)
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="REST API", max_length=160)


class AISDRBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: str
    status: str
    total_count: int
    normalized_count: int
    stored_count: int
    duplicate_count: int
    failed_count: int
    created_by: str
    configuration: dict[str, Any] = Field(validation_alias="source_configuration")
    error: str
    created_at: datetime
    updated_at: datetime


class AISDRRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    batch_id: str
    crm_lead_id: str | None
    source_type: str
    external_id: str
    status: str
    dedupe_key: str
    normalized: dict[str, Any]
    raw: dict[str, Any]
    errors: list[str]
    created_at: datetime
    updated_at: datetime


class AISDRImportResponse(BaseModel):
    batch: AISDRBatchRead
    records: list[AISDRRecordRead] = Field(default_factory=list)


class AISDRImportDetail(AISDRBatchRead):
    records: list[AISDRRecordRead] = Field(default_factory=list)


class AISDRContactSummary(BaseModel):
    id: str
    company: str
    contact: str
    phone: str
    email: str
    industry: str
    status: str
    source: str
    pipeline_stage: str
    next_follow_up: datetime | None
    city: str
    state: str
    country: str
    website: str
    notes: str
    last_contacted_at: datetime | None
    source_record_id: str | None = None
    source_batch_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AISDRDashboardStats(BaseModel):
    total_contacts: int
    ready_to_call: int
    calls_today: int
    interested: int
    qualified: int
    meetings_pending: int
    average_call_duration_seconds: int
    conversion_rate: float


class AISDRDashboardFilters(BaseModel):
    statuses: list[str]
    industries: list[str]
    cities: list[str]
    sources: list[str]


class AISDRDashboardResponse(BaseModel):
    stats: AISDRDashboardStats
    contacts: list[AISDRContactSummary]
    filters: AISDRDashboardFilters
    total: int


class AISDRBulkContactAction(BaseModel):
    contact_ids: list[str] = Field(min_length=1, max_length=500)
    actor: str = Field(default="LeadForge user", max_length=160)


class AISDRBulkActionResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    contact_ids: list[str]


class AISDRConversationStart(BaseModel):
    contact_id: str | None = Field(default=None, max_length=120)
    company: dict[str, Any] = Field(default_factory=dict)
    owner: dict[str, Any] = Field(default_factory=dict)


class AISDRConversationTurn(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class AISDRConversationEvent(BaseModel):
    id: str
    session_id: str
    sequence: int
    event_type: str
    role: str
    state: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AISDRConversationResponse(BaseModel):
    session_id: str
    contact_id: str | None
    state: str
    reply: str
    memory: dict[str, Any]
    events: list[AISDRConversationEvent]


class AISDRCallStart(BaseModel):
    contact_id: str = Field(max_length=120)
    objective: str = Field(default="", max_length=1000)
    actor: str = Field(default="LeadForge user", max_length=160)


class AISDRCustomCallTarget(BaseModel):
    business_name: str = Field(min_length=1, max_length=240)
    owner_name: str = Field(default="", max_length=180)
    phone: str = Field(min_length=3, max_length=80)
    email: str = Field(default="", max_length=320)
    website: str = Field(default="", max_length=500)
    instagram_url: str = Field(default="", max_length=500)
    industry: str = Field(default="", max_length=160)
    city: str = Field(default="", max_length=120)
    offer: str = Field(min_length=1, max_length=2000)
    instructions: str = Field(min_length=1, max_length=5000)
    notes: str = Field(default="", max_length=5000)
    actor: str = Field(default="LeadForge user", max_length=160)


class AISDRCustomCallResponse(BaseModel):
    contact: AISDRContactSummary
    call: AISDRCallSessionRead


class AISDRCallControl(BaseModel):
    action: str = Field(pattern="^(mute|unmute|pause_ai|resume_ai|transfer_to_owner|hang_up|generate_summary)$")
    actor: str = Field(default="LeadForge user", max_length=160)


class AISDRCallTranscriptCreate(BaseModel):
    role: str = Field(pattern="^(customer|ai|system)$")
    text: str = Field(min_length=1, max_length=5000)
    actor: str = Field(default="LeadForge user", max_length=160)


class AISDRCallTranscriptLine(BaseModel):
    role: str
    text: str
    is_final: bool
    confidence: float | None = None
    sequence: int
    created_at: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class AISDRCallOutcomeRead(BaseModel):
    conversation_summary: str
    qualification_score: int
    interested: bool
    reason: str
    objections: list[str]
    website_problems: list[str]
    recommended_services: list[str]
    next_follow_up: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AISDRCallSessionRead(BaseModel):
    id: str
    contact_id: str
    status: str
    provider_call_id: str
    stream_id: str
    objective: str
    telephony_provider: str
    llm_provider: str
    speech_provider: str
    ai_paused: bool
    muted: bool
    transfer_requested: bool
    brain: dict[str, Any]
    outcome: AISDRCallOutcomeRead | None = None
    transcript: list[AISDRCallTranscriptLine]
    duration_seconds: int
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    updated_at: str
