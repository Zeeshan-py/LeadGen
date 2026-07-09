"""AI SDR conversation state machine and orchestration layer.

The manager coordinates memory, sales strategy, qualification, objections, and
closing behavior. It emits structured events for every customer and AI turn and
does not depend on telephony providers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai_sdr.conversation.closing_strategy import ClosingStrategy
from ai_sdr.conversation.company_information import CompanyInformation
from ai_sdr.conversation.memory_extractor import SalesMemoryExtractor
from ai_sdr.conversation.memory_manager import (
    ConversationMemory,
    ConversationMemoryManager,
    default_memory_manager,
)
from ai_sdr.conversation.objection_handler import ObjectionHandler, ObjectionResult
from ai_sdr.conversation.owner_information import OwnerInformation
from ai_sdr.conversation.qualification import QualificationEngine, QualificationResult
from ai_sdr.conversation.response_validator import ResponseValidator
from ai_sdr.conversation.sales_strategy import SalesStrategy
from app.models import Lead, LeadActivity


class ConversationState(str, Enum):
    GREETING = "Greeting"
    PERMISSION = "Permission"
    DISCOVERY = "Discovery"
    QUALIFICATION = "Qualification"
    WEBSITE_DISCUSSION = "Website Discussion"
    AI_AUTOMATION_DISCUSSION = "AI Automation Discussion"
    PRICING = "Pricing"
    OBJECTION_HANDLING = "Objection Handling"
    CLOSING = "Closing"
    FOLLOW_UP = "Follow-up"
    GOODBYE = "Goodbye"


STATE_ORDER = [
    ConversationState.GREETING,
    ConversationState.PERMISSION,
    ConversationState.DISCOVERY,
    ConversationState.QUALIFICATION,
    ConversationState.WEBSITE_DISCUSSION,
    ConversationState.AI_AUTOMATION_DISCUSSION,
    ConversationState.PRICING,
    ConversationState.CLOSING,
    ConversationState.FOLLOW_UP,
    ConversationState.GOODBYE,
]


class AISDRConversationManager:
    """Coordinates AI SDR conversation sessions and state transitions."""

    def __init__(
        self,
        *,
        memory_manager: ConversationMemoryManager | None = None,
        sales_strategy: SalesStrategy | None = None,
        objection_handler: ObjectionHandler | None = None,
        qualification_engine: QualificationEngine | None = None,
        closing_strategy: ClosingStrategy | None = None,
        memory_extractor: SalesMemoryExtractor | None = None,
        response_validator: ResponseValidator | None = None,
    ) -> None:
        self.memory = memory_manager or default_memory_manager
        self.sales = sales_strategy or SalesStrategy()
        self.objections = objection_handler or ObjectionHandler()
        self.qualification = qualification_engine or QualificationEngine()
        self.closing = closing_strategy or ClosingStrategy()
        self.memory_extractor = memory_extractor or SalesMemoryExtractor()
        self.response_validator = response_validator or ResponseValidator()

    def start_for_contact(self, db: Session, contact_id: str) -> dict[str, Any] | None:
        """Start a conversation from an existing CRM contact."""

        lead = db.get(Lead, contact_id)
        if not lead:
            return None
        previous_interactions = self._previous_interactions(db, contact_id, lead)
        return self.start(
            contact_id=contact_id,
            company=CompanyInformation.from_lead(lead, previous_interactions=previous_interactions),
            owner=OwnerInformation.from_lead(lead),
        )

    def start_from_context(
        self,
        *,
        company_payload: dict[str, Any],
        owner_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a conversation from supplied company/owner context."""

        return self.start(
            contact_id=None,
            company=CompanyInformation.from_payload(company_payload),
            owner=OwnerInformation.from_payload(owner_payload or {}),
        )

    def start(
        self,
        *,
        contact_id: str | None,
        company: CompanyInformation,
        owner: OwnerInformation,
    ) -> dict[str, Any]:
        memory = self.memory.create_session(
            contact_id=contact_id,
            company=company,
            owner=owner,
            initial_state=ConversationState.GREETING.value,
        )
        reply = self._validated_reply(self.sales.greeting(company, owner))
        self._record_ai(memory, ConversationState.GREETING, reply, event_type="ai_message")
        self.memory.change_state(
            memory,
            ConversationState.PERMISSION.value,
            reason="Greeting delivered; waiting for permission to continue.",
        )
        self.memory.append_event(
            memory,
            event_type="next_best_question",
            role="system",
            state=memory.state,
            text="Ask for permission before discovery.",
            metadata={"question": "Did I catch you with half a minute?"},
        )
        return self._response(memory, reply=reply)

    def receive_customer_message(self, session_id: str, message: str) -> dict[str, Any] | None:
        """Process one customer message and return the next AI SDR response."""

        memory = self.memory.get(session_id)
        if not memory:
            return None
        cleaned = message.strip()
        self.memory.append_event(
            memory,
            event_type="customer_message",
            role="customer",
            state=memory.state,
            text=cleaned,
            metadata={},
        )
        self._extract_memory(memory, cleaned)

        if self._is_goodbye(cleaned):
            self.memory.change_state(memory, ConversationState.GOODBYE.value, reason="Customer ended the conversation.")
            reply = self._validated_reply(self.closing.goodbye(memory))
            self._record_ai(memory, ConversationState.GOODBYE, reply)
            return self._response(memory, reply=reply)

        objection = self.objections.detect(cleaned, memory)
        if objection.detected:
            return self._handle_objection(memory, objection)

        qualification = self.qualification.evaluate(memory, cleaned)
        self.memory.update_qualification(memory, qualification.to_dict())
        next_state = self._next_state(memory, cleaned, qualification)
        self.memory.change_state(memory, next_state.value, reason="Customer response advanced the state machine.")
        reply = self._reply_for_state(memory, next_state, cleaned, qualification)
        self._record_ai(memory, next_state, reply)
        self._emit_guidance(memory, next_state, qualification)
        return self._response(memory, reply=reply)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        memory = self.memory.get(session_id)
        if not memory:
            return None
        return self._response(memory, reply="")

    def _handle_objection(self, memory: ConversationMemory, objection: ObjectionResult) -> dict[str, Any]:
        self.memory.remember_objection(memory, objection.label)
        self.memory.append_event(
            memory,
            event_type="objection_detected",
            role="system",
            state=memory.state,
            text=objection.label,
            metadata=objection.to_dict(),
        )
        if objection.code == "ai_identity":
            reply = self._validated_reply(objection.reply)
            self.memory.append_event(
                memory,
                event_type="identity_disclosure",
                role="ai",
                state=memory.state,
                text=reply,
                metadata={"honest_ai_disclosure": True},
            )
            return self._response(memory, reply=reply)
        next_state = ConversationState.PRICING if objection.code == "pricing" else ConversationState.OBJECTION_HANDLING
        self.memory.change_state(memory, next_state.value, reason=f"Detected objection: {objection.label}.")
        reply = self._validated_reply(objection.reply)
        self._record_ai(memory, next_state, reply)
        return self._response(memory, reply=reply)

    def _next_state(
        self,
        memory: ConversationMemory,
        message: str,
        qualification: QualificationResult,
    ) -> ConversationState:
        current = ConversationState(memory.state)
        text = message.lower()
        if current in {ConversationState.GREETING, ConversationState.PERMISSION}:
            if self._gave_permission(text):
                return ConversationState.DISCOVERY
            return ConversationState.OBJECTION_HANDLING
        if current == ConversationState.DISCOVERY:
            return ConversationState.QUALIFICATION
        if current == ConversationState.QUALIFICATION:
            return ConversationState.WEBSITE_DISCUSSION
        if current == ConversationState.WEBSITE_DISCUSSION:
            return ConversationState.AI_AUTOMATION_DISCUSSION
        if current == ConversationState.AI_AUTOMATION_DISCUSSION:
            return ConversationState.PRICING if "price" in text or "cost" in text else ConversationState.CLOSING
        if current == ConversationState.PRICING:
            return ConversationState.CLOSING
        if current == ConversationState.OBJECTION_HANDLING:
            return ConversationState.FOLLOW_UP if "send" in text or "later" in text else ConversationState.DISCOVERY
        if current == ConversationState.CLOSING:
            return ConversationState.FOLLOW_UP
        if current == ConversationState.FOLLOW_UP:
            return ConversationState.GOODBYE
        if qualification.is_qualified:
            return ConversationState.CLOSING
        return self._advance(current)

    def _reply_for_state(
        self,
        memory: ConversationMemory,
        state: ConversationState,
        message: str,
        qualification: QualificationResult,
    ) -> str:
        if state == ConversationState.DISCOVERY:
            return self._validated_reply(self.sales.bridge_to_question(
                self.sales.permission_reply(memory),
                self.qualification.discovery_question(memory),
            ))
        if state == ConversationState.QUALIFICATION:
            return self._validated_reply(self.sales.bridge_to_question(
                self.sales.discovery_reply(memory, message),
                self.qualification.qualification_question(memory),
            ))
        if state == ConversationState.WEBSITE_DISCUSSION:
            return self._validated_reply(self.sales.bridge_to_question(
                self.sales.website_discussion(memory),
                "Does that match what you see from customers today?",
            ))
        if state == ConversationState.AI_AUTOMATION_DISCUSSION:
            return self._validated_reply(self.sales.bridge_to_question(
                self.sales.automation_discussion(memory),
                "Where does follow-up currently slow down for your team?",
            ))
        if state == ConversationState.PRICING:
            return self._validated_reply(self.sales.bridge_to_question(
                self.sales.pricing_discussion(memory),
                "Would you want to judge it against missed opportunities rather than a generic feature list?",
            ))
        if state == ConversationState.CLOSING:
            return self._validated_reply(self.closing.next_step_prompt(memory, qualification))
        if state == ConversationState.FOLLOW_UP:
            return self._validated_reply(self.closing.follow_up_prompt(memory))
        if state == ConversationState.GOODBYE:
            return self._validated_reply(self.closing.goodbye(memory))
        if state == ConversationState.OBJECTION_HANDLING:
            return self._validated_reply("I hear you. What would make this useful enough to continue for one more minute?")
        return self._validated_reply(self.sales.permission_reply(memory))

    def _emit_guidance(
        self,
        memory: ConversationMemory,
        state: ConversationState,
        qualification: QualificationResult,
    ) -> None:
        self.memory.append_event(
            memory,
            event_type="qualification_updated",
            role="system",
            state=state.value,
            text=f"Qualification score updated to {qualification.score}.",
            metadata=qualification.to_dict(),
        )
        self.memory.append_event(
            memory,
            event_type="strategy_recommendation",
            role="system",
            state=state.value,
            text=self._strategy_recommendation(state),
            metadata={"state": state.value},
        )

    def _extract_memory(self, memory: ConversationMemory, message: str) -> None:
        self.memory.remember_facts(memory, self.memory_extractor.extract(message))
        text = message.lower()
        for keyword, need in (
            ("booking", "booking friction"),
            ("appointment", "appointment conversion"),
            ("lead", "lead quality"),
            ("inquir", "inquiry follow-up"),
            ("follow", "follow-up speed"),
            ("manual", "manual admin work"),
            ("busy", "time constraint"),
        ):
            if keyword in text:
                self.memory.remember_need(memory, need)
        if "website" in text:
            self.memory.remember_topic(memory, "website")
        if "automation" in text or "ai" in text:
            self.memory.remember_topic(memory, "ai automation")
        if "price" in text or "cost" in text or "budget" in text:
            self.memory.remember_topic(memory, "pricing")

    def _validated_reply(self, reply: str) -> str:
        return self.response_validator.validate(reply)

    def _record_ai(
        self,
        memory: ConversationMemory,
        state: ConversationState,
        reply: str,
        *,
        event_type: str = "ai_message",
    ) -> None:
        self.memory.append_event(
            memory,
            event_type=event_type,
            role="ai",
            state=state.value,
            text=reply,
            metadata={
                "business_name": memory.company.business_name,
                "industry": memory.company.industry,
                "city": memory.company.city,
                "website": memory.company.website,
            },
        )

    def _response(self, memory: ConversationMemory, *, reply: str) -> dict[str, Any]:
        return {
            "session_id": memory.session_id,
            "contact_id": memory.contact_id,
            "state": memory.state,
            "reply": reply,
            "memory": memory.summary(),
            "events": [event.to_dict() for event in memory.events],
        }

    def _previous_interactions(self, db: Session, contact_id: str, lead: Lead) -> list[str]:
        interactions: list[str] = []
        if lead.notes:
            interactions.append(lead.notes.strip())
        rows = db.scalars(
            select(LeadActivity)
            .where(LeadActivity.lead_id == contact_id)
            .order_by(desc(LeadActivity.created_at))
            .limit(3)
        ).all()
        for row in rows:
            text = " - ".join(part for part in (row.title, row.description) if part)
            if text:
                interactions.append(text)
        return list(dict.fromkeys(interactions))

    @staticmethod
    def _advance(current: ConversationState) -> ConversationState:
        index = STATE_ORDER.index(current)
        return STATE_ORDER[min(index + 1, len(STATE_ORDER) - 1)]

    @staticmethod
    def _gave_permission(text: str) -> bool:
        return any(token in text for token in ("yes", "sure", "go ahead", "okay", "ok", "brief", "minute"))

    @staticmethod
    def _is_goodbye(message: str) -> bool:
        text = message.lower()
        return any(token in text for token in ("goodbye", "bye", "stop calling", "remove me", "take me off"))

    @staticmethod
    def _strategy_recommendation(state: ConversationState) -> str:
        return {
            ConversationState.DISCOVERY: "Listen for current lead source, friction, and urgency before pitching.",
            ConversationState.QUALIFICATION: "Confirm need, timing, and decision authority.",
            ConversationState.WEBSITE_DISCUSSION: "Tie the website conversation to conversion, not design taste.",
            ConversationState.AI_AUTOMATION_DISCUSSION: "Position automation as follow-up support, not replacement.",
            ConversationState.PRICING: "Avoid generic pricing; anchor to business impact.",
            ConversationState.CLOSING: "Offer a specific low-friction next step.",
            ConversationState.FOLLOW_UP: "Confirm the follow-up channel and make the recap concrete.",
            ConversationState.GOODBYE: "End politely and respect the customer's preference.",
        }.get(state, "Keep the tone natural, concise, and consultative.")


default_conversation_manager = AISDRConversationManager()
