"""AI SDR production calling orchestration.

This service coordinates telephony media streams, Cartesia speech, Gemini
reasoning, interruption handling, silence detection, and CRM-only persistence.
It never imports or calls Lead Generation services.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ai_sdr.calling.crm_call_gateway import AISDRCallCRMGateway
from ai_sdr.calling.interfaces import (
    AIReasoningContext,
    AIResponse,
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
        self.manual_bridge_calls: dict[str, dict[str, Any]] = {}

    async def start_manual_bridge_call(
        self,
        db: Session,
        *,
        contact_id: str = "",
        to_number: str = "",
        business_name: str = "",
        owner_number: str = "",
        actor: str = "",
    ) -> dict[str, Any]:
        target_number = to_number.strip()
        contact_label = business_name.strip() or "Manual SDR target"
        if contact_id:
            lead = self._require_lead(db, contact_id)
            target_number = target_number or lead.phone
            contact_label = business_name.strip() or lead.business_name
        if not target_number:
            raise ValueError("Manual SDR call target does not have a phone number.")
        owner_number = owner_number.strip() or self.settings.manual_call_owner_number
        if self.settings.calling_mode != "mock":
            self.settings.require_manual_bridge_credentials(owner_number)
        call_id = f"manual-{uuid.uuid4()}"
        actor = actor.strip() or self.settings.default_actor
        request = OutboundCallRequest(
            call_id=call_id,
            contact_id=contact_id or "manual-target",
            to_number=owner_number,
            from_number=self.settings.call_from_number,
            voice_webhook_url=self.settings.manual_bridge_webhook_url(call_id),
            status_callback_url=self.settings.manual_bridge_status_callback_url(call_id),
            media_stream_url="",
            metadata={
                "manual_bridge": True,
                "target_number": target_number,
                "business_name": contact_label,
                "actor": actor,
            },
        )
        self.manual_bridge_calls[call_id] = {
            "id": call_id,
            "contact_id": contact_id,
            "business_name": contact_label,
            "owner_number": owner_number,
            "target_number": target_number,
            "status": "queued",
            "provider_call_id": "",
            "created_at": utc_now().isoformat(),
            "actor": actor,
        }
        result = await self.providers.telephony.start_outbound_call(request)
        self.manual_bridge_calls[call_id].update(
            {
                "status": result.status,
                "provider_call_id": result.provider_call_id,
                "raw": result.raw,
            }
        )
        return dict(self.manual_bridge_calls[call_id])

    def build_manual_bridge_response(self, call_id: str) -> str:
        bridge = self.manual_bridge_calls.get(call_id)
        if not bridge:
            raise LookupError("Manual SDR bridge call not found.")
        target_number = str(bridge.get("target_number") or "")
        if not target_number:
            raise LookupError("Manual SDR bridge call does not have a target number.")
        builder = getattr(self.providers.telephony, "build_manual_bridge_response", None)
        if callable(builder):
            return str(builder(target_number=target_number, caller_id=self.settings.call_from_number))
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Dial callerId="{self.settings.call_from_number}"><Number>{target_number}</Number></Dial></Response>'
        )

    def handle_manual_bridge_status(self, call_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        bridge = self.manual_bridge_calls.get(call_id)
        if not bridge:
            return None
        status = str(payload.get("CallStatus") or payload.get("call_status") or bridge.get("status") or "unknown")
        bridge["status"] = status
        bridge["status_payload"] = payload
        bridge["updated_at"] = utc_now().isoformat()
        return dict(bridge)

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
        if role == "customer" and not session.ai_paused and not session.brain.get("should_end_call"):
            context = self._reasoning_context(lead, session)
            try:
                response = await self.providers.llm.generate_next_response(context)
            except Exception as exc:
                logger.exception(
                    "AI SDR LLM response generation failed during transcript injection; using fallback reply. call_id=%s",
                    session.id,
                )
                response = self._fallback_ai_response(context, error=exc)
            session.update_brain(response)
            self._remember_ai_question(session, response.text)
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
            if (
                segment.role == "customer"
                and segment.is_final
                and not session.ai_paused
                and not session.brain.get("should_end_call")
            ):
                await speech_scheduler(session)

    async def _speak_next(self, websocket: WebSocket, session: AISDRCallSession, *, interrupted: bool) -> None:
        with SessionLocal() as db:
            lead = self._require_lead(db, session.contact_id)
            context = self._reasoning_context(lead, session, interrupted=interrupted)
            if not context.transcript:
                response = self._opening_ai_response(context)
            else:
                try:
                    response = await self.providers.llm.generate_next_response(context)
                except Exception as exc:
                    logger.exception(
                        "AI SDR LLM response generation failed; using fallback reply. call_id=%s",
                        session.id,
                    )
                    response = self._fallback_ai_response(context, error=exc)
            session.update_brain(response)
            self._remember_ai_question(session, response.text)
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

    @staticmethod
    def _opening_ai_response(context: AIReasoningContext) -> AIResponse:
        text = f"Hi, am I speaking with someone from {context.business_name}?"
        return AIResponse(
            text=text,
            current_goal="Confirm the call reached the right business.",
            conversation_stage="Opening",
            detected_objection="None detected",
            customer_sentiment="Neutral",
            qualification_score=20,
            suggested_next_action="Confirm the business before introducing the website offer.",
            should_end_call=False,
            metadata={"provider": "deterministic-opening"},
        )

    @staticmethod
    def _fallback_ai_response(context: AIReasoningContext, *, error: Exception) -> AIResponse:
        customer_turns = [segment.text.lower() for segment in context.transcript if segment.role == "customer"]
        latest = customer_turns[-1] if customer_turns else ""
        all_customer_text = " ".join(customer_turns)
        asked_questions = set(context.memory.get("asked_questions", []))
        awaiting_contact = "contact_details" in asked_questions or "website_type_answer" in asked_questions
        if any(token in latest for token in ("bye", "goodbye", "stop calling")):
            text = "No problem. Thanks for your time, and have a good day."
            should_end = True
            stage = "Goodbye"
        elif not latest:
            response = AISDRCallingOrchestrator._opening_ai_response(context)
            return AIResponse(
                text=response.text,
                current_goal=response.current_goal,
                conversation_stage=response.conversation_stage,
                detected_objection=response.detected_objection,
                customer_sentiment=response.customer_sentiment,
                qualification_score=response.qualification_score,
                suggested_next_action=response.suggested_next_action,
                should_end_call=False,
                metadata={"provider": "fallback", "error": str(error), "reason": "opening"},
            )
        elif any(token in latest for token in ("again", "same question", "why are you asking")):
            text = "You're right, apologies. I called because I saw no website listed for you on Google Maps."
            should_end = False
            stage = "Website Discussion"
        elif _asks_website_capability(latest):
            if "website_type_answer" in asked_questions:
                text = _website_type_repeat_text(context)
            else:
                text = _website_type_answer_text(context)
            should_end = False
            stage = "Website Discussion"
        elif _mentions_pricing(latest):
            text = (
                "I do not want to give a random price on the call. "
                "Please share your best number, and my owner will talk to you about requirements and pricing."
            )
            should_end = False
            stage = "Pricing"
        elif _mentions_wrong_industry(latest, context):
            text = (
                f"You're right, apologies. I mean a website for {context.business_name}, "
                f"focused on {_industry_focus(context)}, not a restaurant website."
            )
            should_end = False
            stage = "Website Discussion"
        elif _is_negative(latest):
            text = _future_contact_goodbye_text()
            should_end = True
            stage = "Goodbye"
        elif _is_identity_question(latest):
            if "business_confirm" in asked_questions:
                text = (
                    f"This is Ava with LeadForge. I saw {context.business_name} on Google Maps "
                    "and could not find a proper website listed."
                )
            else:
                text = f"Hi, this is Ava with LeadForge. Am I speaking with someone from {context.business_name}?"
            should_end = False
            stage = "Opening"
        elif _is_business_confirmation(latest) and "google_maps_no_website" not in asked_questions:
            text = (
                f"Thanks. I saw {context.business_name} on Google Maps and noticed no proper website was listed."
            )
            should_end = False
            stage = "Website Discussion"
        elif _is_low_information(latest) and "google_maps_no_website" not in asked_questions:
            text = f"No problem. I just wanted to confirm this is {context.business_name} before I explain quickly."
            should_end = False
            stage = "Opening"
        elif "google_maps_no_website" in asked_questions and "interest_check" not in asked_questions:
            text = _interest_pitch_text(context)
            should_end = False
            stage = "Offer"
        elif awaiting_contact and _mentions_contact_detail(latest):
            text = "Perfect. We'll contact you for requirements and start with the first version. Thanks for your time."
            should_end = True
            stage = "Goodbye"
        elif awaiting_contact and _mentions_partial_contact_detail(latest):
            text = "I only caught part of that. Please say the full phone number, including the starting digits."
            should_end = False
            stage = "Follow-up"
        elif "contact_details" in asked_questions:
            text = (
                "No problem. Please share the full best phone number, and my owner will contact you "
                "to understand requirements and discuss the next step."
            )
            should_end = False
            stage = "Follow-up"
        elif _is_permission(latest) and "interest_check" in asked_questions:
            text = (
                "Great. What number should we contact? We'll ask your requirements, "
                "make the first version first, and then discuss the amount further."
            )
            should_end = False
            stage = "Follow-up"
        elif _is_low_information(latest) and "website_type_answer" in asked_questions:
            text = (
                "Yes, I'm here. If that type of website sounds useful, share your best number "
                "and we'll discuss your requirements."
            )
            should_end = False
            stage = "Follow-up"
        elif _is_low_information(latest) and "interest_check" in asked_questions:
            text = "Yes, I'm here. If you're interested, share your best number and we'll discuss requirements."
            should_end = False
            stage = "Follow-up"
        elif any(token in all_customer_text for token in ("reservation", "instagram", "whatsapp")):
            text = _interest_pitch_text(context)
            should_end = False
            stage = "Offer"
        else:
            text = _contextual_fallback_text(context, asked_questions)
            should_end = False
            stage = "Offer"
        return AIResponse(
            text=text,
            current_goal="Keep the call moving with a short fallback reply.",
            conversation_stage=stage,
            detected_objection="None detected",
            customer_sentiment="Neutral",
            qualification_score=30,
            suggested_next_action="Recover the conversation and ask one simple question.",
            should_end_call=should_end,
            metadata={"provider": "fallback", "error": str(error)},
        )

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
                "asked_questions": session.memory.get("asked_questions", []),
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
    def _remember_ai_question(session: AISDRCallSession, text: str) -> None:
        label = _classify_ai_question(text)
        if not label:
            return
        asked_questions = session.memory.setdefault("asked_questions", [])
        if label not in asked_questions:
            asked_questions.append(label)
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


def _classify_ai_question(text: str) -> str:
    lowered = text.lower()
    if "speaking with someone from" in lowered:
        return "business_confirm"
    if "google maps" in lowered and "website" in lowered:
        return "google_maps_no_website"
    if "are you interested" in lowered or "would be useful for you" in lowered or "would that be useful" in lowered:
        return "interest_check"
    if "helps people see your menu" in lowered or "show your portfolio" in lowered or "show your services" in lowered:
        return "website_benefit"
    if any(
        token in lowered
        for token in (
            "menu, photos, location",
            "portfolio, project gallery",
            "services, work, location",
            "mobile-friendly",
        )
    ):
        return "website_type_answer"
    if any(
        token in lowered
        for token in (
            "what number should we contact",
            "please share your best number",
            "share your best number",
            "best phone number",
            "best whatsapp",
            "best email",
            "sending examples",
        )
    ):
        return "contact_details"
    return ""


def _is_business_confirmation(text: str) -> bool:
    return any(
        token in text
        for token in (
            "yes",
            "sure",
            "please",
            "go ahead",
            "okay",
            "ok",
            "speaking",
            "this is",
            "we have attention",
            "let's see",
            "lets see",
        )
    )


def _is_permission(text: str) -> bool:
    return any(
        token in text
        for token in (
            "yes",
            "sure",
            "please",
            "go ahead",
            "okay",
            "ok",
            "interested",
            "we have attention",
        )
    )


def _mentions_pricing(text: str) -> bool:
    return any(token in text for token in ("cost", "price", "pricing", "amount", "charge", "charges", "budget"))


def _asks_website_capability(text: str) -> bool:
    if "website" not in text and "site" not in text:
        return False
    return any(
        token in text
        for token in (
            "what type",
            "which type",
            "what kind",
            "which kind",
            "what sort",
            "can you make",
            "can you build",
            "what can you make",
            "what can you build",
            "what features",
            "features",
            "included",
            "include",
        )
    )


def _is_identity_question(text: str) -> bool:
    return any(token in text for token in ("who is", "who are", "other side"))


def _mentions_wrong_industry(text: str, context: AIReasoningContext) -> bool:
    return "restaurant" in text and _industry_kind(context) != "restaurant"


def _is_negative(text: str) -> bool:
    cleaned = " ".join(text.replace(".", " ").replace(",", " ").replace("!", " ").split())
    return cleaned in {"no", "no thanks", "not now"} or any(
        token in cleaned
        for token in ("not interested", "don't need", "do not need", "no need", "already have")
    )


def _is_low_information(text: str) -> bool:
    cleaned = " ".join(text.replace(".", " ").replace(",", " ").split())
    return cleaned in {"oh", "uh", "um", "hmm", "hello", "hello hello"}


def _mentions_contact_source(text: str) -> bool:
    return any(
        token in text
        for token in (
            "instagram",
            "reservation",
            "reservations",
            "booking",
            "whatsapp",
            "phone",
            "call",
            "dm",
            "walk in",
            "walk-in",
        )
    )


def _mentions_contact_detail(text: str) -> bool:
    return _digit_count(text) >= 7 or "@" in text


def _mentions_partial_contact_detail(text: str) -> bool:
    return 1 <= _digit_count(text) < 7 or any(
        token in text for token in ("my number", "number is", "phone is", "contact is")
    )


def _digit_count(text: str) -> int:
    return sum(char.isdigit() for char in text)


def _interest_pitch_text(context: AIReasoningContext) -> str:
    benefit = _website_benefit_text(context)
    return (
        f"{benefit} I'm a graduate engineer and web developer, I've completed many projects, "
        "and I can make an attractive website for you. Are you interested?"
    )


def _future_contact_goodbye_text() -> str:
    return (
        "No problem. Thanks for your time. If you ever need a website developer "
        "or any tech help, you can contact us."
    )


def _reason_for_call_text(context: AIReasoningContext) -> str:
    return f"I will be brief. The reason for my call is a modern website for {context.business_name}."


def _contextual_fallback_text(context: AIReasoningContext, asked_questions: set[str]) -> str:
    if "website_type_answer" in asked_questions:
        return "That is the main idea. If it sounds useful, share your best number and we'll discuss requirements."
    if "interest_check" in asked_questions:
        return "Sure. Are you interested in us making that website for you?"
    if "google_maps_no_website" in asked_questions:
        return _interest_pitch_text(context)
    return _reason_for_call_text(context)


def _website_type_answer_text(context: AIReasoningContext) -> str:
    if _industry_kind(context) == "restaurant":
        return (
            f"For {context.business_name}, I can make a modern restaurant website with menu, photos, "
            "location map, WhatsApp/contact, and booking or reservation enquiry. "
            "If useful, share your best number."
        )
    if _industry_kind(context) == "architecture":
        return (
            f"For {context.business_name}, I can make a portfolio website with project gallery, services, "
            "about section, location, WhatsApp/contact, and enquiry form. If useful, share your best number."
        )
    return (
        f"For {context.business_name}, I can make a modern mobile-friendly website with services, work, "
        "map location, WhatsApp/contact, and enquiry form. If useful, share your best number."
    )


def _website_type_repeat_text(context: AIReasoningContext) -> str:
    if _industry_kind(context) == "restaurant":
        return (
            "It would be a restaurant website: menu, photos, location, WhatsApp/contact, "
            "and booking enquiry. Share your best number and we'll discuss requirements."
        )
    if _industry_kind(context) == "architecture":
        return (
            "It would be an architecture portfolio website: projects, services, profile, "
            "contact details, and enquiry form. Share your best number and we'll discuss requirements."
        )
    return (
        "It would be a business website with your services, work, location, contact options, "
        "and enquiry form. Share your best number and we'll discuss requirements."
    )


def _website_benefit_text(context: AIReasoningContext) -> str:
    if _industry_kind(context) == "restaurant":
        return "A website can show your menu, photos, location, and reservations in one place."
    if _industry_kind(context) == "architecture":
        return "A website can show your portfolio, services, projects, and enquiry options clearly."
    return "A website can show your services, work, location, and contact options clearly."


def _industry_focus(context: AIReasoningContext) -> str:
    if _industry_kind(context) == "architecture":
        return "your portfolio, services, projects, and enquiries"
    if _industry_kind(context) == "restaurant":
        return "your menu, photos, location, and reservations"
    return "your services, work, contact details, and customer enquiries"


def _industry_kind(context: AIReasoningContext) -> str:
    text = " ".join(
        [
            context.business_name,
            context.industry,
            context.objective,
        ]
    ).lower()
    if any(token in text for token in ("restaurant", "cafe", "food", "dining")):
        return "restaurant"
    if any(token in text for token in ("architect", "architecture", "interior", "design studio")):
        return "architecture"
    return "generic"
