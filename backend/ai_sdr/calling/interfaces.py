"""Provider contracts for AI SDR calling.

The calling runtime depends only on these interfaces. Twilio, Gemini, and
Cartesia are implementations, not architectural assumptions, so another
telephony, LLM, or speech provider can be introduced behind the same methods.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Base exception for provider failures surfaced to the orchestrator."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is selected but required credentials are missing."""


@dataclass(frozen=True)
class OutboundCallRequest:
    """Provider-neutral request to place a phone call."""

    call_id: str
    contact_id: str
    to_number: str
    from_number: str
    voice_webhook_url: str
    status_callback_url: str
    media_stream_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundCallResult:
    """Provider-neutral result returned after an outbound call is created."""

    provider_call_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TelephonyMediaEvent:
    """Normalized event received from a telephony media WebSocket."""

    event_type: str
    call_id: str
    provider_call_id: str
    stream_id: str
    audio: bytes = b""
    timestamp_ms: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CallStatusUpdate:
    """Normalized call lifecycle update from the telephony provider."""

    provider_call_id: str
    status: str
    duration_seconds: int | None = None
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TranscriptSegment:
    """One recognized or generated sentence in a call transcript."""

    role: str
    text: str
    is_final: bool = True
    confidence: float | None = None
    sequence: int = 0
    provider_event_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class AIReasoningContext:
    """Context passed to an LLM provider for the next AI response."""

    call_id: str
    contact_id: str
    business_name: str
    owner_name: str
    industry: str
    city: str
    website: str
    objective: str
    transcript: list[TranscriptSegment]
    memory: dict[str, Any]
    interrupted: bool = False
    assistant_name: str = ""
    assistant_business_name: str = ""
    ai_greeting: str = ""


@dataclass(frozen=True)
class AIResponse:
    """Provider-neutral next AI utterance and live brain state."""

    text: str
    current_goal: str
    conversation_stage: str
    detected_objection: str
    customer_sentiment: str
    qualification_score: int
    suggested_next_action: str
    should_end_call: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CallOutcome:
    """Structured end-of-call result stored in CRM."""

    conversation_summary: str
    qualification_score: int
    interested: bool
    reason: str
    objections: list[str] = field(default_factory=list)
    website_problems: list[str] = field(default_factory=list)
    recommended_services: list[str] = field(default_factory=list)
    next_follow_up: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SpeechRecognitionSession(Protocol):
    """Streaming speech recognizer session used by telephony media streams."""

    async def send_audio(self, audio: bytes) -> None:
        """Send one audio frame from the telephony stream to the recognizer."""

    async def receive_segments(self) -> AsyncIterator[TranscriptSegment]:
        """Yield transcript segments as the recognizer produces them."""

    async def finalize_utterance(self) -> None:
        """Ask the provider to finalize the current utterance after silence."""

    async def close(self) -> None:
        """Close provider resources associated with the recognition stream."""


@runtime_checkable
class TelephonyProvider(Protocol):
    """Abstract telephony provider used by the AI SDR calling runtime."""

    name: str

    async def start_outbound_call(self, request: OutboundCallRequest) -> OutboundCallResult:
        """Place an outbound call and return the provider call identifier."""

    async def end_call(self, provider_call_id: str) -> None:
        """End an active provider call."""

    def build_voice_response(self, *, call_id: str, media_stream_url: str) -> str:
        """Build provider instructions that connect the call to a media stream."""

    def parse_status_update(self, payload: dict[str, Any]) -> CallStatusUpdate:
        """Normalize a provider status webhook payload."""

    def parse_media_event(self, payload: dict[str, Any]) -> TelephonyMediaEvent:
        """Normalize a provider media WebSocket payload."""

    def outbound_audio_message(self, *, stream_id: str, audio: bytes) -> dict[str, Any]:
        """Build a WebSocket message that sends synthesized audio to the call."""

    def clear_audio_message(self, *, stream_id: str) -> dict[str, Any]:
        """Build a WebSocket message that clears queued provider audio."""


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract reasoning provider used by the AI SDR call brain."""

    name: str

    async def generate_next_response(self, context: AIReasoningContext) -> AIResponse:
        """Generate the next natural AI SDR response."""

    async def summarize_call(self, context: AIReasoningContext) -> CallOutcome:
        """Generate the final structured call outcome."""


@runtime_checkable
class SpeechProvider(Protocol):
    """Abstract speech provider for transcription, synthesis, and silence."""

    name: str

    async def create_recognition_session(self, *, call_id: str) -> SpeechRecognitionSession:
        """Create a streaming speech recognition session."""

    async def synthesize_stream(self, *, text: str, call_id: str) -> AsyncIterator[bytes]:
        """Stream synthesized speech audio bytes for the telephony provider."""

    def is_silence(self, audio: bytes) -> bool:
        """Return whether a telephony frame appears silent."""
