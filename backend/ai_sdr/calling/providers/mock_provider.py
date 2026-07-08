"""Mock calling providers for local development and deterministic tests."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

from ai_sdr.calling.interfaces import (
    AIReasoningContext,
    AIResponse,
    CallOutcome,
    CallStatusUpdate,
    LLMProvider,
    OutboundCallRequest,
    OutboundCallResult,
    SpeechProvider,
    SpeechRecognitionSession,
    TelephonyMediaEvent,
    TelephonyProvider,
    TranscriptSegment,
)


class MockTelephonyProvider(TelephonyProvider):
    """Deterministic telephony provider that never reaches a carrier."""

    name = "mock"

    async def start_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        return OutboundCallResult(
            provider_call_id=f"mock-call-{uuid.uuid4()}",
            status="queued",
            raw={"request": request.metadata},
        )

    async def end_call(self, provider_call_id: str) -> None:
        return None

    def build_voice_response(self, *, call_id: str, media_stream_url: str) -> str:
        return f"<Response><Say>Mock AI SDR call {call_id}</Say></Response>"

    def parse_status_update(self, payload: dict[str, Any]) -> CallStatusUpdate:
        return CallStatusUpdate(
            provider_call_id=str(payload.get("provider_call_id") or "mock"),
            status=str(payload.get("status") or "completed"),
            duration_seconds=int(payload.get("duration_seconds") or 0),
            raw=payload,
        )

    def parse_media_event(self, payload: dict[str, Any]) -> TelephonyMediaEvent:
        return TelephonyMediaEvent(
            event_type=str(payload.get("event") or "media"),
            call_id=str(payload.get("call_id") or ""),
            provider_call_id=str(payload.get("provider_call_id") or ""),
            stream_id=str(payload.get("stream_id") or ""),
            audio=bytes(payload.get("audio") or b""),
            raw=payload,
        )

    def outbound_audio_message(self, *, stream_id: str, audio: bytes) -> dict[str, Any]:
        return {"event": "mock_audio", "stream_id": stream_id, "bytes": len(audio)}

    def clear_audio_message(self, *, stream_id: str) -> dict[str, Any]:
        return {"event": "mock_clear", "stream_id": stream_id}


class MockLLMProvider(LLMProvider):
    """Rule-based LLM provider used when real Gemini credentials are absent."""

    name = "mock"

    async def generate_next_response(self, context: AIReasoningContext) -> AIResponse:
        latest_customer = next((line.text for line in reversed(context.transcript) if line.role == "customer"), "")
        interested = any(word in latest_customer.lower() for word in ("yes", "open", "interested", "send", "useful"))
        return AIResponse(
            text=(
                f"That is helpful context for {context.business_name}. "
                "Would it make sense to schedule a short review of the website and follow-up process?"
            ),
            current_goal="Qualify need and secure the next step.",
            conversation_stage="Closing" if interested else "Discovery",
            detected_objection="None detected",
            customer_sentiment="Interested" if interested else "Neutral",
            qualification_score=78 if interested else 52,
            suggested_next_action="Offer a focused follow-up time.",
            should_end_call=False,
            metadata={"provider": self.name},
        )

    async def summarize_call(self, context: AIReasoningContext) -> CallOutcome:
        transcript_text = " ".join(line.text for line in context.transcript if line.role == "customer")
        interested = any(word in transcript_text.lower() for word in ("yes", "open", "interested", "send", "tomorrow"))
        return CallOutcome(
            conversation_summary=f"Mock AI SDR call completed for {context.business_name}.",
            qualification_score=82 if interested else 45,
            interested=interested,
            reason="Customer showed positive next-step language." if interested else "No clear buying signal captured.",
            objections=[],
            website_problems=["Booking path needs review"] if context.website else [],
            recommended_services=["Website conversion audit", "AI follow-up automation"],
            next_follow_up="Send two follow-up times by email." if interested else "",
            metadata={"provider": self.name},
        )


class MockSpeechProvider(SpeechProvider):
    """Speech provider that emits no real audio and accepts injected transcripts."""

    name = "mock"

    async def create_recognition_session(self, *, call_id: str) -> SpeechRecognitionSession:
        return MockRecognitionSession()

    async def synthesize_stream(self, *, text: str, call_id: str) -> AsyncIterator[bytes]:
        yield text.encode("utf-8")

    def is_silence(self, audio: bytes) -> bool:
        return not audio or all(byte == 0 for byte in audio)


class MockRecognitionSession(SpeechRecognitionSession):
    """Recognition session that stays open until closed by the caller."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[TranscriptSegment | None] = asyncio.Queue()

    async def send_audio(self, audio: bytes) -> None:
        return None

    async def receive_segments(self) -> AsyncIterator[TranscriptSegment]:
        while True:
            segment = await self._queue.get()
            if segment is None:
                break
            yield segment

    async def finalize_utterance(self) -> None:
        return None

    async def close(self) -> None:
        await self._queue.put(None)
