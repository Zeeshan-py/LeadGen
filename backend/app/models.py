"""Core SQLAlchemy data model for the LeadForge platform.

These ORM classes define the CRM-centered persistence model: campaigns, leads,
users, tags, notes, activities, outreach, synced email messages, analytics,
runtime settings, and background generation jobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
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


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    provider: Mapped[str] = mapped_column(String(40), default="email", index=True)
    provider_id: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[str] = mapped_column(String(800), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    gmail_connections: Mapped[list["GmailConnection"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    twilio_connections: Mapped[list["TwilioConnection"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    voice_settings: Mapped["VoiceSettings | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    paddle_customers: Mapped[list["PaddleCustomer"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    paddle_subscriptions: Mapped[list["PaddleSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    paddle_transactions: Mapped[list["PaddleTransaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class GmailConnection(Base, TimestampMixin):
    __tablename__ = "gmail_connections"
    __table_args__ = (UniqueConstraint("user_id", name="uq_gmail_connections_user_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    gmail_email: Mapped[str] = mapped_column(String(320), default="", index=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    scopes: Mapped[str] = mapped_column(Text, default="")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")

    user: Mapped[User] = relationship(back_populates="gmail_connections")


class TwilioConnection(Base, TimestampMixin):
    __tablename__ = "twilio_connections"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    account_sid: Mapped[str] = mapped_column(String(80), default="", index=True)
    auth_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    phone_number: Mapped[str] = mapped_column(String(40), default="", index=True)
    phone_sid: Mapped[str] = mapped_column(String(80), default="")
    friendly_name: Mapped[str] = mapped_column(String(160), default="")
    account_status: Mapped[str] = mapped_column(String(40), default="")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(500), default="")

    user: Mapped[User] = relationship(back_populates="twilio_connections")


class VoiceSettings(Base, TimestampMixin):
    __tablename__ = "voice_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_voice_settings_user_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    voice_provider: Mapped[str] = mapped_column(String(40), default="cartesia")
    voice_id: Mapped[str] = mapped_column(String(160), default="")
    voice_name: Mapped[str] = mapped_column(String(160), default="")
    speaking_speed: Mapped[str] = mapped_column(String(20), default="normal")
    language: Mapped[str] = mapped_column(String(20), default="en")
    ai_greeting: Mapped[str] = mapped_column(Text, default="")
    business_name: Mapped[str] = mapped_column(String(160), default="")
    assistant_name: Mapped[str] = mapped_column(String(120), default="")
    cartesia_api_key_encrypted: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="voice_settings")


class PaddleCustomer(Base, TimestampMixin):
    __tablename__ = "paddle_customers"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_paddle_customers_customer_id"),
        UniqueConstraint("user_id", name="uq_paddle_customers_user_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(String(80), index=True)
    email: Mapped[str] = mapped_column(String(320), default="", index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[User | None] = relationship(back_populates="paddle_customers")


class PaddleSubscription(Base, TimestampMixin):
    __tablename__ = "paddle_subscriptions"
    __table_args__ = (UniqueConstraint("subscription_id", name="uq_paddle_subscriptions_subscription_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subscription_id: Mapped[str] = mapped_column(String(80), index=True)
    customer_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="", index=True)
    plan_key: Mapped[str] = mapped_column(String(60), default="", index=True)
    price_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    product_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    currency_code: Mapped[str] = mapped_column(String(10), default="")
    billing_interval: Mapped[str] = mapped_column(String(20), default="")
    billing_frequency: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_change_action: Mapped[str] = mapped_column(String(40), default="")
    scheduled_change_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    management_urls: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    custom_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[User | None] = relationship(back_populates="paddle_subscriptions")


class PaddleTransaction(Base, TimestampMixin):
    __tablename__ = "paddle_transactions"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_paddle_transactions_transaction_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    transaction_id: Mapped[str] = mapped_column(String(80), index=True)
    customer_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    subscription_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="", index=True)
    invoice_number: Mapped[str] = mapped_column(String(80), default="", index=True)
    currency_code: Mapped[str] = mapped_column(String(10), default="")
    subtotal: Mapped[str] = mapped_column(String(40), default="")
    tax: Mapped[str] = mapped_column(String(40), default="")
    total: Mapped[str] = mapped_column(String(40), default="")
    billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    invoice_url: Mapped[str] = mapped_column(String(1000), default="")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[User | None] = relationship(back_populates="paddle_transactions")


class PaddleWebhookEvent(Base):
    __tablename__ = "paddle_webhook_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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


class CrmUser(Base, TimestampMixin):
    __tablename__ = "crm_users"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_crm_users_user_email"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(320), default="", index=True)
    initials: Mapped[str] = mapped_column(String(8), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    assigned_leads: Mapped[list["Lead"]] = relationship(back_populates="assigned_user")


class CrmTag(Base, TimestampMixin):
    __tablename__ = "crm_tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_crm_tags_user_name"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    color: Mapped[str] = mapped_column(String(40), default="")

    lead_links: Mapped[list["LeadTag"]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_leads_user_dedupe_key"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), index=True)
    business_name: Mapped[str] = mapped_column(String(240), index=True)
    contact_name: Mapped[str] = mapped_column(String(180), default="", index=True)
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
    crm_stage: Mapped[str] = mapped_column(String(40), default="qualified", index=True)
    outreach_status: Mapped[str] = mapped_column(String(40), default="not_started", index=True)
    assigned_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("crm_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    social_links: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    social_status: Mapped[str] = mapped_column(String(40), default="missing", index=True)
    screenshot_url: Mapped[str] = mapped_column(String(800), default="")
    source: Mapped[str] = mapped_column(String(80), default="apify_google_maps")
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    campaign: Mapped[Campaign | None] = relationship(back_populates="leads")
    assigned_user: Mapped[CrmUser | None] = relationship(back_populates="assigned_leads")
    outreach_items: Mapped[list["Outreach"]] = relationship(back_populates="lead")
    crm_tag_links: Mapped[list["LeadTag"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    crm_notes: Mapped[list["LeadNote"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    crm_activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    email_messages: Mapped[list["EmailMessage"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )


class LeadTag(Base):
    __tablename__ = "lead_tags"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("crm_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    lead: Mapped[Lead] = relationship(back_populates="crm_tag_links")
    tag: Mapped[CrmTag] = relationship(back_populates="lead_links")


class LeadNote(Base, TimestampMixin):
    __tablename__ = "lead_notes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
    )
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(160), default="LeadForge user")

    lead: Mapped[Lead] = relationship(back_populates="crm_notes")


class LeadActivity(Base):
    __tablename__ = "lead_activities"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(160), default="LeadForge AI")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    lead: Mapped[Lead] = relationship(back_populates="crm_activities")


class Outreach(Base, TimestampMixin):
    __tablename__ = "outreach"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    email_messages: Mapped[list["EmailMessage"]] = relationship(back_populates="outreach")


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "gmail_message_id", name="uq_email_messages_user_gmail_message_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
    )
    outreach_id: Mapped[str | None] = mapped_column(
        ForeignKey("outreach.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gmail_message_id: Mapped[str] = mapped_column(String(255), index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    message_id_header: Mapped[str] = mapped_column(String(500), default="")
    direction: Mapped[str] = mapped_column(String(20), index=True)
    from_email: Mapped[str] = mapped_column(String(320), default="")
    to_email: Mapped[str] = mapped_column(String(320), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    lead: Mapped[Lead] = relationship(back_populates="email_messages")
    outreach: Mapped[Outreach | None] = relationship(back_populates="email_messages")


class Analytics(Base):
    __tablename__ = "analytics"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Setting(Base):
    __tablename__ = "settings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeadGenerationJob(Base):
    __tablename__ = "lead_generation_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
