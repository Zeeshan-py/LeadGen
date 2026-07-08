"""Supported AI SDR source descriptors."""

from __future__ import annotations

from ai_sdr.schemas import AISDRSourceDescriptor, AISDRSourceType


def supported_sources() -> list[AISDRSourceDescriptor]:
    return [
        AISDRSourceDescriptor(
            type=AISDRSourceType.CSV,
            label="CSV",
            status="adapter_ready",
            entrypoint="/ai-sdr/imports",
            notes="Accepts extracted row dictionaries from CSV ingestion workers.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.EXCEL,
            label="Excel",
            status="adapter_ready",
            entrypoint="/ai-sdr/imports",
            notes="Accepts extracted workbook row dictionaries from Excel ingestion workers.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.GOOGLE_SHEETS,
            label="Google Sheets",
            status="adapter_ready",
            entrypoint="/ai-sdr/imports",
            notes="Accepts sheet rows after Google Sheets authorization and range selection.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.MANUAL_ENTRY,
            label="Manual Entry",
            status="live",
            entrypoint="/ai-sdr/contacts/manual",
            notes="Stores one operator-entered contact through the SDR normalization pipeline.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.REST_API,
            label="REST API",
            status="live",
            entrypoint="/ai-sdr/contacts",
            notes="Stores API-submitted contacts through the SDR normalization pipeline.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.CRM,
            label="CRM",
            status="adapter_ready",
            entrypoint="/ai-sdr/imports",
            notes="Accepts CRM-origin records for re-normalization or future enrichment workflows.",
        ),
        AISDRSourceDescriptor(
            type=AISDRSourceType.FUTURE_INTEGRATION,
            label="Future Integrations",
            status="extension_point",
            entrypoint="/ai-sdr/imports",
            notes="Reserved source type for new connectors that emit contact dictionaries.",
        ),
    ]
