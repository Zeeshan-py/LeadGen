"""AI SDR production calling orchestration.

This service coordinates telephony media streams, Cartesia speech, Gemini
reasoning, interruption handling, silence detection, and CRM-only persistence.
It never imports or calls Lead Generation services.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ai_sdr.calling.crm_call_gateway import AISDRCallCRMGateway
from ai_sdr.calling.interfaces import (
    AIReasoningContext,
    CallOutcome,
    OutboundCallRequest,
    ProviderConfigurationError,
    ProviderError,
    TranscriptSegment,
)
from ai_sdr.calling.providers import CallingProviderStack, build_calling_provider_stack
from ai_sdr.calling.session_manager import (
    AISDRCallSession,
    AISDRCallSessionRegistry,
    default_call_session_registry,
    utc_now,
)
from ai_sdr.calling.silence import SilenceDetector
from ai_sdr.config import AISDRSettings, get_ai_sdr_settings
from ai_sdr.conversation.memory_extractor import ExtractedFacts, SalesMemoryExtractor
from app.database import SessionLocal
from app.models import Lead


logger = logging.getLogger(__name__)


class AISDRCallingOrchestrator:
    """Coordinates production AI SDR calls across providers and CRM."""

    def __init__(
        self,
        *,
        settings: AISDRSettings | None = None,
        providers: CallingProviderStack | None = None,
        registry: AISDRCallSessionRegistry | None = None,
    ) -> None:
        self.settings = settings or get_ai_sdr_settings()
        self.providers = providers or build_calling_provider_stack(self.settings)
        self.registry = registry or default_call_session_registry
        self.memory_extractor = SalesMemoryExtractor()

    async def start_outbound_call(
        self,
        db: Session,
        *,
        contact_id: str,
        objective: str = "",
        actor: str = "",
    ) -> AISDRCallSession:
        if not self.settings.calling_enabled:
            raise RuntimeError("AI SDR calling is disabled.")
        if self.settings.calling_mode != "mock":
            self.settings.require_calling_credentials()

        lead = db.get(Lead, contact_id)
        if not lead:
            raise LookupError("AI SDR CRM contact not found.")
        if not lead.phone:
            raise ValueError("AI SDR contact does not have a phone number.")

        session = self.registry.create(
            contact_id=lead.id,
            objective=(objective.strip() or self.settings.call_default_objective),
            telephony_provider=self.providers.telephony.name,
            llm_provider=self.providers.llm.name,
            speech_provider=self.providers.speech.name,
        )
        session.status = "queued"
        actor = actor.strip() or self.settings.default_actor
        AISDRCallCRMGateway(db).record_call_started(lead, session, actor=actor)
        request = OutboundCallRequest(
            call_id=session.id,
            contact_id=lead.id,
            to_number=lead.phone,
            from_number=self.settings.call_from_number,
            voice_webhook_url=self.settings.voice_webhook_url(session.id),
            status_callback_url=self.settings.status_callback_url(session.id),
            media_stream_url=self.settings.media_stream_url(session.id),
            metadata={
                "business_name": lead.business_name,
                "industry": lead.business_type,
                "city": lead.city,
                "website": lead.website,
            },
        )
        result = await self.providers.telephony.start_outbound_call(request)
        self.registry.bind_provider_call(session, result.provider_call_id)
        session.status = result.status
        session.updated_at = utc_now()
        db.add(lead)
        db.commit()
        return session

    def get_session(self, call_id: str) -> AISDRCallSession | None:
        return self.registry.get(call_id)

    def list_sessions(self) -> list[AISDRCallSession]:
        return self.registry.all()

    def build_voice_response(self, call_id: str) -> str:
        session = self.registry.get(call_id)
        if not session:
            raise LookupError("AI SDR call session not found.")
        return self.providers.telephony.build_voice_response(
            call_id=call_id,
            media_stream_url=self.settings.media_stream_url(call_id),
        )

    async def handle_status_update(
        self,
        db: Session,
        *,
        call_id: str,
        payload: dict[str, Any],
        actor: str = "",
    ) -> AISDRCallSession | None:
        update = self.providers.telephony.parse_status_update(payload)
        session = self.registry.get(call_id) or self.registry.get_by_provider_call_id(update.provider_call_id)
        if not session:
            return None
        if update.provider_call_id and not session.provider_call_id:
            self.registry.bind_provider_call(session, update.provider_call_id)
        session.status = update.status
        session.updated_at = utc_now()
        if update.status in {"in-progress", "answered"} and not session.started_at:
            session.started_at = utc_now()
        if update.status in {"completed", "busy", "failed", "no-answer", "canceled"}:
            await self.complete_call(
                db,
                call_id=session.id,
                actor=actor or self.settings.default_actor,
                failure_reason=update.reason if update.status != "completed" else "",
            )
        db.commit()
        return session

    async def control_call(
        self,
        db: Session,
        *,
        call_id: str,
        action: str,
        actor: str = "",
    ) -> AISDRCallSession:
        session = self._require_session(call_id)
        lead = self._require_lead(db, session.contact_id)
        actor = actor.strip() or self.settings.default_actor
        action = action.strip().lower().replace("-", "_")
        if action == "mute":
            session.muted = True
        elif action == "unmute":
            session.muted = False
        elif action == "pause_ai":
            session.ai_paused = True
        elif action == "resume_ai":
            session.ai_paused = False
        elif action == "transfer_to_owner":
            session.transfer_requested = True
        elif action == "hang_up":
            if session.provider_call_id:
                await self.providers.telephony.end_call(session.provider_call_id)
            await self.complete_call(db, call_id=call_id, actor=actor)
        elif action == "generate_summary":
            await self.complete_call(db, call_id=call_id, actor=actor, keep_open=True)
        else:
            raise ValueError(f"Unsupported AI SDR call control action: {action}")
        AISDRCallCRMGateway(db).record_control_event(lead, session, action=action, actor=actor)
        db.commit()
        return session

    async def inject_transcript(
        self,
        db: Session,
        *,
        call_id: str,
        role: str,
        text: str,
        actor: str = "",
    ) -> AISDRCallSession:
        """Testing hook that exercises transcript, reasoning, and CRM storage."""

        session = self._require_session(call_id)
        lead = self._require_lead(db, session.contact_id)
        actor = actor.strip() or self.settings.default_actor
        segment = session.append_transcript(TranscriptSegment(role=role, text=text))
        if segment.role == "customer":
            self._remember_customer_facts(session, segment.text)
        AISDRCallCRMGateway(db).record_transcript_segment(lead, session, segment, actor=actor)
        if role == "customer" and not session.ai_paused:
            response = await self.providers.llm.generate_next_response(self._reasoning_context(lead, session))
            session.update_brain(response)
            ai_segment = session.append_transcript(TranscriptSegment(role="ai", text=response.text))
            AISDRCallCRMGateway(db).record_transcript_segment(lead, session, ai_segment, actor=actor)
        db.commit()
        return session

    async def complete_call(
        self,
        db: Session,
        *,
        call_id: str,
        actor: str = "",
        failure_reason: str = "",
        keep_open: bool = False,
    ) -> AISDRCallSession:
        session = self._require_session(call_id)
        lead = self._require_lead(db, session.contact_id)
        actor = actor.strip() or self.settings.default_actor
        if failure_reason:
            AISDRCallCRMGateway(db).record_call_failed(lead, session, reason=failure_reason, actor=actor)
            db.commit()
            return session

        outcome = await self._summarize(lead, session)
        session.outcome = outcome
        if not keep_open:
            session.status = "completed"
            session.ended_at = session.ended_at or datetime.now(timezone.utc)
        AISDRCallCRMGateway(db).record_call_completed(lead, session, outcome, actor=actor)
        db.commit()
        return session

    async def handle_twilio_media_stream(self, websocket: WebSocket) -> None:
        await websocket.accept()
        call_id = str(websocket.query_params.get("call_id") or "")
        session = self.registry.get(call_id) if call_id else None
        recognition: Any | None = None
        silence: SilenceDetector | None = None
        transcript_task: asyncio.Task[None] | None = None
        active_speech_task: asyncio.Task[None] | None = None

        async def schedule_speech(current_session: AISDRCallSession, *, interrupted: bool = False) -> None:
            nonlocal active_speech_task
            if active_speech_task is not None and not active_speech_task.done():
                active_speech_task.cancel()
                with suppress(asyncio.CancelledError):
                    await active_speech_task
            active_speech_task = asyncio.create_task(
                self._speak_next(websocket, current_session, interrupted=interrupted)
            )
            active_speech_task.add_done_callback(self._log_background_task_error)

        try:
            async for payload in self._websocket_payloads(websocket):
                media_event = self.providers.telephony.parse_media_event(payload)
                if media_event.call_id:
                    session = self._require_session(media_event.call_id)
                if session is None:
                    if media_event.event_type == "start":
                        raise LookupError("Twilio media stream did not include AI SDR call_id parameter.")
                    continue
                if media_event.provider_call_id and not session.provider_call_id:
                    self.registry.bind_provider_call(session, media_event.provider_call_id)
                if media_event.stream_id:
                    session.stream_id = media_event.stream_id
                if media_event.event_type == "start":
                    recognition = await self.providers.speech.create_recognition_session(call_id=session.id)
                    silence = SilenceDetector(
                        self.providers.speech,
                        timeout_seconds=self.settings.call_silence_timeout_seconds,
                    )
                    transcript_task = asyncio.create_task(
                        self._consume_recognition(session, recognition, websocket, schedule_speech)
                    )
                    await self._mark_connected(session)
                    await schedule_speech(session, interrupted=False)
                elif media_event.event_type == "media":
                    if session is None or recognition is None or silence is None:
                        continue
                    is_voice, should_finalize = silence.observe(media_event.audio)
                    if is_voice:
                        session.last_customer_audio_at = utc_now()
                        if session.ai_speaking:
                            if active_speech_task is not None and not active_speech_task.done():
                                active_speech_task.cancel()
                            await self._interrupt_ai(websocket, session)
                    await recognition.send_audio(media_event.audio)
                    if should_finalize:
                        session.silence_finalized_at = utc_now()
                        await recognition.finalize_utterance()
                elif media_event.event_type == "stop":
                    break
        except WebSocketDisconnect:
            logger.info("AI SDR Twilio media stream disconnected call_id=%s", call_id or "<missing>")
            return
        except Exception:
            logger.exception(
                "AI SDR Twilio media stream failed call_id=%s provider_call_id=%s",
                session.id if session else call_id or "<missing>",
                session.provider_call_id if session else "",
            )
            raise
        finally:
            if recognition is not None:
                await recognition.close()
            if active_speech_task is not None:
                active_speech_task.cancel()
                with suppress(asyncio.CancelledError):
                    await active_speech_task
            if transcript_task is not None:
                transcript_task.cancel()
                with suppress(asyncio.CancelledError):
                    await transcript_task
            if session is not None:
                with SessionLocal() as db:
                    if session.status not in {"completed", "failed"}:
                        await self.complete_call(db, call_id=session.id, actor=self.settings.default_actor)

    async def _consume_recognition(
        self,
        session: AISDRCallSession,
        recognition: Any,
        websocket: WebSocket,
        speech_scheduler: Callable[[AISDRCallSession], Awaitable[None]],
    ) -> None:
        async for segment in recognition.receive_segments():
            if not segment.text.strip():
                continue
            with SessionLocal() as db:
                lead = self._require_lead(db, session.contact_id)
                saved = session.append_transcript(segment)
                if saved.role == "customer":
                    self._remember_customer_facts(session, saved.text)
                AISDRCallCRMGateway(db).record_transcript_segment(
                    lead,
                    session,
                    saved,
                    actor=self.settings.default_actor,
                )
                db.commit()
            if segment.role == "customer" and segment.is_final and not session.ai_paused:
                await speech_scheduler(session)

    async def _speak_next(self, websocket: WebSocket, session: AISDRCallSession, *, interrupted: bool) -> None:
        with SessionLocal() as db:
            lead = self._require_lead(db, session.contact_id)
            response = await self.providers.llm.generate_next_response(
                self._reasoning_context(lead, session, interrupted=interrupted)
            )
            session.update_brain(response)
            segment = session.append_transcript(TranscriptSegment(role="ai", text=response.text))
            AISDRCallCRMGateway(db).record_transcript_segment(
                lead,
                session,
                segment,
                actor=self.settings.default_actor,
            )
            db.commit()
        await self._send_speech(websocket, session, response.text)
        if response.should_end_call:
            await self.providers.telephony.end_call(session.provider_call_id)

    async def _send_speech(self, websocket: WebSocket, session: AISDRCallSession, text: str) -> None:
        if session.ai_paused or not session.stream_id:
            return
        session.ai_speaking = True
        try:
            async for audio in self.providers.speech.synthesize_stream(text=text, call_id=session.id):
                if not session.ai_speaking:
                    break
                await websocket.send_json(
                    self.providers.telephony.outbound_audio_message(stream_id=session.stream_id, audio=audio)
                )
        except asyncio.CancelledError:
            session.ai_speaking = False
            raise
        except (ProviderConfigurationError, ProviderError):
            raise
        finally:
            session.ai_speaking = False

    async def _interrupt_ai(self, websocket: WebSocket, session: AISDRCallSession) -> None:
        session.ai_speaking = False
        if session.stream_id:
            await websocket.send_json(self.providers.telephony.clear_audio_message(stream_id=session.stream_id))
        with SessionLocal() as db:
            lead = self._require_lead(db, session.contact_id)
            AISDRCallCRMGateway(db).record_control_event(
                lead,
                session,
                action="interruption_detected",
                actor=self.settings.default_actor,
            )
            db.commit()

    async def _mark_connected(self, session: AISDRCallSession) -> None:
        session.status = "in-progress"
        session.started_at = session.started_at or utc_now()
        with SessionLocal() as db:
            lead = self._require_lead(db, session.contact_id)
            AISDRCallCRMGateway(db).record_call_connected(lead, session, actor=self.settings.default_actor)
            db.commit()

    async def _summarize(self, lead: Lead, session: AISDRCallSession) -> CallOutcome:
        if session.outcome:
            return session.outcome
        try:
            return await self.providers.llm.summarize_call(self._reasoning_context(lead, session))
        except ProviderError:
            raise
        except Exception as exc:
            return CallOutcome(
                conversation_summary=f"AI SDR call ended for {lead.business_name}. Summary generation failed.",
                qualification_score=0,
                interested=False,
                reason=f"Summary generation failed: {exc}",
                metadata={"error": str(exc)},
            )

    def _reasoning_context(
        self,
        lead: Lead,
        session: AISDRCallSession,
        *,
        interrupted: bool = False,
    ) -> AIReasoningContext:
        return AIReasoningContext(
            call_id=session.id,
            contact_id=lead.id,
            business_name=lead.business_name,
            owner_name=lead.contact_name or "the owner",
            industry=lead.business_type,
            city=lead.city,
            website=lead.website,
            objective=session.objective,
            transcript=session.transcript,
            memory={
                "crm_stage": lead.crm_stage,
                "notes": lead.notes,
                "website_summary": lead.website_summary,
                "website_problems": lead.website_problems,
                "previous_ai_sdr": (lead.raw or {}).get("ai_sdr", {}),
                "brain": session.brain,
                "facts": session.memory.get("facts", {}),
            },
            interrupted=interrupted,
        )

    def _remember_customer_facts(self, session: AISDRCallSession, text: str) -> None:
        facts = self.memory_extractor.extract(text)
        existing = self._facts_from_session(session)
        existing.merge(facts)
        session.memory["facts"] = existing.to_dict()
        session.updated_at = utc_now()

    @staticmethod
    def _facts_from_session(session: AISDRCallSession) -> ExtractedFacts:
        values = session.memory.get("facts", {})
        facts = ExtractedFacts()
        if not isinstance(values, dict):
            return facts
        for key, value in values.items():
            if hasattr(facts, key):
                setattr(facts, key, value)
        return facts

    @staticmethod
    def _log_background_task_error(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        with suppress(asyncio.CancelledError):
            exc = task.exception()
            if exc is not None:
                logger.error(
                    "AI SDR background speech task failed.",
                    exc_info=(type(exc), exc, exc.__traceback__),
                )

    @staticmethod
    async def _websocket_payloads(websocket: WebSocket) -> Any:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
            text = message.get("text")
            if text is None and message.get("bytes") is not None:
                text = message["bytes"].decode("utf-8")
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload

    def _require_session(self, call_id: str) -> AISDRCallSession:
        session = self.registry.get(call_id)
        if not session:
            raise LookupError("AI SDR call session not found.")
        return session

    @staticmethod
    def _require_lead(db: Session, contact_id: str) -> Lead:
        lead = db.get(Lead, contact_id)
        if not lead:
            raise LookupError("AI SDR CRM contact not found.")
        return lead


default_calling_orchestrator = AISDRCallingOrchestrator()
