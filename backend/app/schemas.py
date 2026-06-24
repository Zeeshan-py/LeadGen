from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateLeadRequest(BaseModel):
    continent: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=120)
    business_type: str = Field(min_length=1, max_length=160)
    max_leads: int = Field(default=50, ge=1, le=500)
    website_mode: str = Field(default="withWebsite", pattern="^(allPlaces|withWebsite|withoutWebsite)$")
    campaign_name: str | None = Field(default=None, max_length=180)

    @field_validator("continent", "country", "business_type", "campaign_name")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())


class JobCreated(BaseModel):
    job_id: str
    status: str
    events_url: str


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str | None
    business_name: str
    website: str
    google_maps_url: str
    email: str
    phone: str
    location: str
    city: str
    state: str
    country: str
    business_type: str
    website_score: int
    opportunity_score: int
    website_problems: list[str]
    website_summary: str
    improvement_suggestions: list[str]
    lead_status: str
    outreach_status: str
    notes: str
    tags: list[str]
    social_links: dict[str, str]
    social_status: str
    screenshot_url: str
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    business_name: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    lead_status: str | None = None
    outreach_status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    city: str = ""
    state: str = ""
    country: str = ""
    business_type: str = ""
    max_leads: int = Field(default=50, ge=1, le=500)


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    city: str
    state: str
    country: str
    business_type: str
    status: str
    max_leads: int
    leads_generated: int
    emails_sent: int
    replies: int
    created_at: datetime
    updated_at: datetime


class OutreachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    campaign_id: str | None
    subject_line: str
    personalized_first_line: str
    cold_email: str
    follow_up_1: str
    follow_up_2: str
    selected_version: str
    status: str
    gmail_message_id: str
    gmail_thread_id: str
    tracking_id: str
    sent_at: datetime | None
    opened_at: datetime | None
    replied_at: datetime | None
    bounced_at: datetime | None
    failed_reason: str
    created_at: datetime
    updated_at: datetime


class SendEmailRequest(BaseModel):
    outreach_id: str
    version: str = Field(default="cold_email", pattern="^(cold_email|follow_up_1|follow_up_2)$")


class SettingsPayload(BaseModel):
    gemini_api_key: str | None = None
    apify_api_key: str | None = None
    google_sheets_id: str | None = None
    gmail_credentials: dict[str, Any] | None = None
    default_lead_limit: int | None = Field(default=None, ge=1, le=500)
    export_settings: dict[str, Any] | None = None


class AnalyticsResponse(BaseModel):
    leads_found: int
    leads_saved: int
    emails_found: int
    social_links_found: int
    failed_leads: int
    total_leads_generated: int
    emails_sent: int
    replies_received: int
    open_rate: float
    website_opportunities_found: int
    conversion_rate: float
    lead_generation_per_day: list[dict[str, Any]]
    emails_per_day: list[dict[str, Any]]
    top_cities: list[dict[str, Any]]
    top_niches: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
