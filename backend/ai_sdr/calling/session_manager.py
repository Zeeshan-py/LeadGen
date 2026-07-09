"""In-memory runtime state for active AI SDR phone calls."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_sdr.calling.interfaces import AIResponse, CallOutcome, TranscriptSegment


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AISDRCallSession:
    """Process-local state for one active or recently completed AI SDR call."""

    id: str
    contact_id: str
    objective: str
    status: str = "created"
    provider_call_id: str = ""
    stream_id: str = ""
    telephony_provider: str = ""
    llm_provider: str = ""
    speech_provider: str = ""
    transcript: list[TranscriptSegment] = field(default_factory=list)
    brain: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    outcome: CallOutcome | None = None
    ai_paused: bool = False
    muted: bool = False
    transfer_requested: bool = False
    ai_speaking: bool = False
    last_customer_audio_at: datetime | None = None
    silence_finalized_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def append_transcript(self, segment: TranscriptSegment) -> TranscriptSegment:
        sequence = len(self.transcript) + 1
        stamped = TranscriptSegment(
            role=segment.role,
            text=segment.text,
            is_final=segment.is_final,
            confidence=segment.confidence,
            sequence=sequence,
            provider_event_id=segment.provider_event_id,
            raw=segment.raw,
            created_at=segment.created_at or utc_now(),
        )
        self.transcript.append(stamped)
        self.updated_at = stamped.created_at or utc_now()
        return stamped

    def update_brain(self, response: AIResponse) -> None:
        self.brain = {
            "current_goal": response.current_goal,
            "conversation_stage": response.conversation_stage,
            "detected_objection": response.detected_objection,
            "customer_sentiment": response.customer_sentiment,
            "qualification_score": response.qualification_score,
            "suggested_next_action": response.suggested_next_action,
            "should_end_call": response.should_end_call,
            "provider": response.metadata.get("provider"),
        }
        self.updated_at = utc_now()

    def duration_seconds(self) -> int:
        start = self.started_at or self.created_at
        end = self.ended_at or utc_now()
        return max(0, int((end - start).total_seconds()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "status": self.status,
            "provider_call_id": self.provider_call_id,
            "stream_id": self.stream_id,
            "objective": self.objective,
            "telephony_provider": self.telephony_provider,
            "llm_provider": self.llm_provider,
            "speech_provider": self.speech_provider,
            "ai_paused": self.ai_paused,
            "muted": self.muted,
            "transfer_requested": self.transfer_requested,
            "brain": self.brain,
            "memory": self.memory,
            "outcome": self.outcome.__dict__ if self.outcome else None,
            "transcript": [
                {
                    "role": segment.role,
                    "text": segment.text,
                    "is_final": segment.is_final,
                    "confidence": segment.confidence,
                    "sequence": segment.sequence,
                    "created_at": segment.created_at.isoformat() if segment.created_at else None,
                    "raw": segment.raw,
                }
                for segment in self.transcript
            ],
            "duration_seconds": self.duration_seconds(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "updated_at": self.updated_at.isoformat(),
        }


class AISDRCallSessionRegistry:
    """Process-local registry for active calls and provider IDs."""

    def __init__(self) -> None:
        self._sessions: dict[str, AISDRCallSession] = {}
        self._provider_index: dict[str, str] = {}

    def create(
        self,
        *,
        contact_id: str,
        objective: str,
        telephony_provider: str,
        llm_provider: str,
        speech_provider: str,
    ) -> AISDRCallSession:
        session = AISDRCallSession(
            id=str(uuid.uuid4()),
            contact_id=contact_id,
            objective=objective,
            telephony_provider=telephony_provider,
            llm_provider=llm_provider,
            speech_provider=speech_provider,
        )
        self._sessions[session.id] = session
        return session

    def get(self, call_id: str) -> AISDRCallSession | None:
        return self._sessions.get(call_id)

    def get_by_provider_call_id(self, provider_call_id: str) -> AISDRCallSession | None:
        call_id = self._provider_index.get(provider_call_id)
        return self._sessions.get(call_id) if call_id else None

    def bind_provider_call(self, session: AISDRCallSession, provider_call_id: str) -> None:
        session.provider_call_id = provider_call_id
        if provider_call_id:
            self._provider_index[provider_call_id] = session.id
        session.updated_at = utc_now()

    def all(self) -> list[AISDRCallSession]:
        return list(self._sessions.values())


default_call_session_registry = AISDRCallSessionRegistry()
