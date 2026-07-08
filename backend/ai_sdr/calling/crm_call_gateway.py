"""CRM persistence boundary for AI SDR phone calls."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ai_sdr.calling.interfaces import CallOutcome, TranscriptSegment
from ai_sdr.calling.session_manager import AISDRCallSession
from app.models import Lead
from app.services.crm import change_crm_stage, mark_contacted, record_crm_activity, replace_lead_tags


class AISDRCallCRMGateway:
    """Stores call transcripts, summaries, and outcomes through CRM APIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_call_started(self, lead: Lead, session: AISDRCallSession, *, actor: str) -> None:
        mark_contacted(lead)
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_started",
            title="AI SDR call started",
            description=session.objective,
            actor=actor,
            metadata=self._base_metadata(session),
        )

    def record_call_connected(self, lead: Lead, session: AISDRCallSession, *, actor: str) -> None:
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_connected",
            title="AI SDR call connected",
            actor=actor,
            metadata=self._base_metadata(session),
        )

    def record_transcript_segment(
        self,
        lead: Lead,
        session: AISDRCallSession,
        segment: TranscriptSegment,
        *,
        actor: str,
    ) -> None:
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_transcript",
            title=f"AI SDR transcript: {segment.role}",
            description=segment.text,
            actor=actor,
            metadata={
                **self._base_metadata(session),
                "role": segment.role,
                "sequence": segment.sequence,
                "is_final": segment.is_final,
                "confidence": segment.confidence,
                "provider_event_id": segment.provider_event_id,
                "raw": segment.raw,
            },
        )

    def record_control_event(
        self,
        lead: Lead,
        session: AISDRCallSession,
        *,
        action: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_control",
            title=f"AI SDR call control: {action}",
            actor=actor,
            metadata={**self._base_metadata(session), "action": action, **(metadata or {})},
        )

    def record_call_completed(
        self,
        lead: Lead,
        session: AISDRCallSession,
        outcome: CallOutcome,
        *,
        actor: str,
    ) -> None:
        session.outcome = outcome
        session.ended_at = session.ended_at or datetime.now(timezone.utc)
        lead.raw = self._merged_raw(lead, session, outcome)
        if outcome.website_problems:
            lead.website_problems = outcome.website_problems
        if outcome.recommended_services:
            lead.improvement_suggestions = outcome.recommended_services
        follow_up = _parse_follow_up(outcome.next_follow_up)
        if follow_up:
            lead.next_follow_up_at = follow_up

        next_stage = self._stage_for_outcome(outcome)
        if lead.crm_stage not in {"won", "archived"}:
            change_crm_stage(
                self.db,
                lead,
                next_stage,
                actor=actor,
                description=outcome.reason,
            )
        tags = list(lead.tags or [])
        tags.extend(["AI SDR Called", "Interested" if outcome.interested else "Not Interested"])
        if outcome.qualification_score >= 70:
            tags.append("AI SDR Qualified")
        replace_lead_tags(self.db, lead, tags, actor=actor)
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_completed",
            title="AI SDR call completed",
            description=outcome.conversation_summary,
            actor=actor,
            metadata={
                **self._base_metadata(session),
                "duration_seconds": session.duration_seconds(),
                "conversation_summary": outcome.conversation_summary,
                "qualification_score": outcome.qualification_score,
                "interested": outcome.interested,
                "reason": outcome.reason,
                "objections": outcome.objections,
                "website_problems": outcome.website_problems,
                "recommended_services": outcome.recommended_services,
                "next_follow_up": outcome.next_follow_up,
                "transcript": self._transcript_payload(session),
            },
        )

    def record_call_failed(
        self,
        lead: Lead,
        session: AISDRCallSession,
        *,
        reason: str,
        actor: str,
    ) -> None:
        session.status = "failed"
        session.ended_at = session.ended_at or datetime.now(timezone.utc)
        record_crm_activity(
            self.db,
            lead_id=lead.id,
            event_type="ai_sdr_call_failed",
            title="AI SDR call failed",
            description=reason,
            actor=actor,
            metadata={**self._base_metadata(session), "reason": reason},
        )

    @staticmethod
    def _stage_for_outcome(outcome: CallOutcome) -> str:
        if outcome.interested and outcome.qualification_score >= 70:
            return "interested"
        if outcome.qualification_score >= 70:
            return "qualified"
        return "lost"

    @staticmethod
    def _base_metadata(session: AISDRCallSession) -> dict[str, Any]:
        return {
            "ai_sdr_call_id": session.id,
            "provider_call_id": session.provider_call_id,
            "stream_id": session.stream_id,
            "telephony_provider": session.telephony_provider,
            "llm_provider": session.llm_provider,
            "speech_provider": session.speech_provider,
            "status": session.status,
        }

    @staticmethod
    def _transcript_payload(session: AISDRCallSession) -> list[dict[str, Any]]:
        return [
            {
                "role": segment.role,
                "text": segment.text,
                "sequence": segment.sequence,
                "is_final": segment.is_final,
                "created_at": segment.created_at.isoformat() if segment.created_at else None,
            }
            for segment in session.transcript
        ]

    def _merged_raw(self, lead: Lead, session: AISDRCallSession, outcome: CallOutcome) -> dict[str, Any]:
        raw = dict(lead.raw or {})
        ai_sdr = dict(raw.get("ai_sdr") or {})
        calls = list(ai_sdr.get("calls") or [])
        call_payload = {
            "call_id": session.id,
            "provider_call_id": session.provider_call_id,
            "status": session.status,
            "duration_seconds": session.duration_seconds(),
            "objective": session.objective,
            "outcome": {
                "conversation_summary": outcome.conversation_summary,
                "qualification_score": outcome.qualification_score,
                "interested": outcome.interested,
                "reason": outcome.reason,
                "objections": outcome.objections,
                "website_problems": outcome.website_problems,
                "recommended_services": outcome.recommended_services,
                "next_follow_up": outcome.next_follow_up,
            },
            "transcript": self._transcript_payload(session),
        }
        calls.append(call_payload)
        ai_sdr["last_call"] = call_payload
        ai_sdr["calls"] = calls[-10:]
        raw["ai_sdr"] = ai_sdr
        return raw


def _parse_follow_up(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
