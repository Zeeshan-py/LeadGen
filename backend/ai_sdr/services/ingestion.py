"""AI SDR ingestion service.

Creates import batches, normalizes records, writes contacts into CRM through
the module gateway, and stores batch/record accounting for auditability.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from ai_sdr.config import get_ai_sdr_settings
from ai_sdr.infrastructure.crm_gateway import AISDRCRMGateway
from ai_sdr.models import AISDRContactBatch, AISDRContactRecord
from ai_sdr.schemas import (
    AISDRBatchRead,
    AISDRImportCreate,
    AISDRImportDetail,
    AISDRImportResponse,
    AISDRImportStatus,
    AISDRRecordRead,
    AISDRRecordStatus,
    AISDRSourceType,
)
from ai_sdr.services.normalization import contact_to_raw_payload, normalize_contact


class AISDRIngestionService:
    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id
        self.settings = get_ai_sdr_settings()

    def ingest_contacts(self, payload: AISDRImportCreate) -> AISDRImportResponse:
        if not self.settings.enabled:
            raise RuntimeError("AI SDR is disabled.")
        if len(payload.contacts) > self.settings.max_contacts_per_import:
            raise ValueError(
                f"AI SDR imports are limited to {self.settings.max_contacts_per_import} contacts."
            )

        batch = AISDRContactBatch(
            user_id=self.user_id,
            source_type=payload.source_type.value,
            status=AISDRImportStatus.PROCESSING.value,
            total_count=len(payload.contacts),
            created_by=payload.created_by.strip() or self.settings.default_actor,
            source_configuration=payload.configuration,
        )
        self.db.add(batch)
        self.db.flush()

        gateway = AISDRCRMGateway(self.db, self.user_id)
        for contact in payload.contacts:
            raw_payload = contact_to_raw_payload(contact)
            record = AISDRContactRecord(
                user_id=self.user_id,
                batch_id=batch.id,
                source_type=payload.source_type.value,
                external_id=str(raw_payload.get("external_id") or raw_payload.get("externalId") or ""),
                raw=raw_payload if self.settings.store_raw_payloads else {},
            )
            self.db.add(record)
            self.db.flush()

            normalized = normalize_contact(contact, payload.source_type)
            record.normalized = normalized.to_record()
            record.dedupe_key = normalized.dedupe_key
            if normalized.errors:
                record.status = AISDRRecordStatus.FAILED.value
                record.errors = normalized.errors
                batch.failed_count += 1
                continue

            batch.normalized_count += 1
            result = gateway.upsert_contact(
                normalized,
                batch_id=batch.id,
                record_id=record.id,
                actor=batch.created_by,
            )
            record.crm_lead_id = result.lead.id
            record.status = AISDRRecordStatus.STORED.value if result.created else AISDRRecordStatus.DUPLICATE.value
            batch.stored_count += 1
            if not result.created:
                batch.duplicate_count += 1

        batch.status = self._final_status(batch).value
        self.db.commit()
        return self._response(batch)

    def list_batches(
        self,
        *,
        source_type: AISDRSourceType | None = None,
        status: AISDRImportStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AISDRBatchRead]:
        query = (
            select(AISDRContactBatch)
            .where(AISDRContactBatch.user_id == self.user_id)
            .order_by(desc(AISDRContactBatch.created_at))
        )
        if source_type:
            query = query.where(AISDRContactBatch.source_type == source_type.value)
        if status:
            query = query.where(AISDRContactBatch.status == status.value)
        rows = self.db.scalars(query.offset(offset).limit(limit)).all()
        return [AISDRBatchRead.model_validate(row) for row in rows]

    def get_batch(self, batch_id: str) -> AISDRImportDetail | None:
        batch = self.db.scalar(
            select(AISDRContactBatch)
            .options(selectinload(AISDRContactBatch.records))
            .where(AISDRContactBatch.id == batch_id, AISDRContactBatch.user_id == self.user_id)
        )
        if not batch:
            return None
        return AISDRImportDetail(
            **AISDRBatchRead.model_validate(batch).model_dump(),
            records=[
                AISDRRecordRead.model_validate(record)
                for record in sorted(batch.records, key=lambda item: item.created_at)
            ],
        )

    @staticmethod
    def _final_status(batch: AISDRContactBatch) -> AISDRImportStatus:
        if batch.failed_count == batch.total_count:
            return AISDRImportStatus.FAILED
        if batch.failed_count:
            return AISDRImportStatus.COMPLETED_WITH_ERRORS
        return AISDRImportStatus.COMPLETED

    @staticmethod
    def _response(batch: AISDRContactBatch) -> AISDRImportResponse:
        return AISDRImportResponse(
            batch=AISDRBatchRead.model_validate(batch),
            records=[
                AISDRRecordRead.model_validate(record)
                for record in sorted(batch.records, key=lambda item: item.created_at)
            ],
        )
