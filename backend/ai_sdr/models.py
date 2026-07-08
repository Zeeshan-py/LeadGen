"""AI SDR-owned persistence models.

The module stores import batch and per-record metadata here while normalized
contacts themselves are written to the shared CRM ``leads`` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


class AISDRTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AISDRContactBatch(Base, AISDRTimestampMixin):
    __tablename__ = "ai_sdr_contact_batches"
    __table_args__ = (
        Index("ix_ai_sdr_contact_batches_source_status", "source_type", "status"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    normalized_count: Mapped[int] = mapped_column(Integer, default=0)
    stored_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(160), default="LeadForge AI SDR")
    source_configuration: Mapped[dict[str, Any]] = mapped_column("configuration", JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")

    records: Mapped[list["AISDRContactRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class AISDRContactRecord(Base, AISDRTimestampMixin):
    __tablename__ = "ai_sdr_contact_records"
    __table_args__ = (
        Index("ix_ai_sdr_contact_records_batch_status", "batch_id", "status"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("ai_sdr_contact_batches.id", ondelete="CASCADE"),
        index=True,
    )
    crm_lead_id: Mapped[str | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="received", index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)

    batch: Mapped[AISDRContactBatch] = relationship(back_populates="records")
