from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    continent: Mapped[str] = mapped_column(String(80), default="")
    business_type: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    max_leads: Mapped[int] = mapped_column(Integer, default=50)
    leads_generated: Mapped[int] = mapped_column(Integer, default=0)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)

    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign")
    outreach: Mapped[list["Outreach"]] = relationship(back_populates="campaign")


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_leads_dedupe_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), index=True)
    business_name: Mapped[str] = mapped_column(String(240), index=True)
    website: Mapped[str] = mapped_column(String(500), default="")
    google_maps_url: Mapped[str] = mapped_column(String(800), default="")
    email: Mapped[str] = mapped_column(String(320), default="", index=True)
    phone: Mapped[str] = mapped_column(String(80), default="")
    location: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    business_type: Mapped[str] = mapped_column(String(160), default="", index=True)
    website_score: Mapped[int] = mapped_column(Integer, default=0)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    website_problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    website_summary: Mapped[str] = mapped_column(Text, default="")
    improvement_suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    lead_status: Mapped[str] = mapped_column(String(40), default="qualified", index=True)
    outreach_status: Mapped[str] = mapped_column(String(40), default="not_started", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    social_links: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    social_status: Mapped[str] = mapped_column(String(40), default="missing", index=True)
    screenshot_url: Mapped[str] = mapped_column(String(800), default="")
    source: Mapped[str] = mapped_column(String(80), default="apify_google_maps")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    campaign: Mapped[Campaign | None] = relationship(back_populates="leads")
    outreach_items: Mapped[list["Outreach"]] = relationship(back_populates="lead")


class Outreach(Base, TimestampMixin):
    __tablename__ = "outreach"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    subject_line: Mapped[str] = mapped_column(String(220), default="")
    personalized_first_line: Mapped[str] = mapped_column(Text, default="")
    cold_email: Mapped[str] = mapped_column(Text, default="")
    follow_up_1: Mapped[str] = mapped_column(Text, default="")
    follow_up_2: Mapped[str] = mapped_column(Text, default="")
    selected_version: Mapped[str] = mapped_column(String(40), default="cold_email")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), default="")
    gmail_thread_id: Mapped[str] = mapped_column(String(255), default="")
    tracking_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_reason: Mapped[str] = mapped_column(Text, default="")

    lead: Mapped[Lead] = relationship(back_populates="outreach_items")
    campaign: Mapped[Campaign | None] = relationship(back_populates="outreach")


class Analytics(Base):
    __tablename__ = "analytics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeadGenerationJob(Base):
    __tablename__ = "lead_generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    continent: Mapped[str] = mapped_column(String(80), default="")
    business_type: Mapped[str] = mapped_column(String(160), default="")
    website_mode: Mapped[str] = mapped_column(String(40), default="withWebsite")
    max_leads: Mapped[int] = mapped_column(Integer, default=50)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    lead_counter: Mapped[int] = mapped_column(Integer, default=0)
    success_counter: Mapped[int] = mapped_column(Integer, default=0)
    failure_counter: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
