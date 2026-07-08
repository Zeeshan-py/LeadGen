"""In-memory conversation storage for AI SDR sessions.

This module stores active session context, transcript events, discovered needs,
objections, qualification notes, and summaries. Persistence can be added later
behind the same manager interface.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_sdr.conversation.company_information import CompanyInformation
from ai_sdr.conversation.owner_information import OwnerInformation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConversationEvent:
    """Structured event emitted by the AI SDR conversation engine."""

    id: str
    session_id: str
    sequence: int
    event_type: str
    role: str
    state: str
    text: str
    metadata: dict[str, Any]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event into an API-safe dictionary."""

        return {
            "id": self.id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "role": self.role,
            "state": self.state,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ConversationMemory:
    """In-memory session state for one AI SDR conversation."""

    session_id: str
    contact_id: str | None
    company: CompanyInformation
    owner: OwnerInformation
    state: str
    events: list[ConversationEvent] = field(default_factory=list)
    discovered_needs: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    qualification_notes: dict[str, Any] = field(default_factory=dict)
    quoted_topics: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def transcript(self) -> list[dict[str, Any]]:
        """Return customer/AI transcript lines without system-only events."""

        return [
            {
                "role": event.role,
                "state": event.state,
                "text": event.text,
                "created_at": event.created_at.isoformat(),
            }
            for event in self.events
            if event.event_type in {"customer_message", "ai_message"}
        ]

    def summary(self) -> dict[str, Any]:
        """Return compact session memory for API consumers and UI panels."""

        return {
            "session_id": self.session_id,
            "contact_id": self.contact_id,
            "state": self.state,
            "business_name": self.company.business_name,
            "owner_name": self.owner.name,
            "discovered_needs": self.discovered_needs,
            "objections": self.objections,
            "qualification": self.qualification_notes,
            "quoted_topics": self.quoted_topics,
            "previous_interactions": self.company.previous_interactions,
            "event_count": len(self.events),
            "updated_at": self.updated_at.isoformat(),
        }


class ConversationMemoryManager:
    """Process-local repository for active conversation sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationMemory] = {}

    def create_session(
        self,
        *,
        contact_id: str | None,
        company: CompanyInformation,
        owner: OwnerInformation,
        initial_state: str,
    ) -> ConversationMemory:
        """Create a new in-memory conversation session."""

        session_id = str(uuid.uuid4())
        memory = ConversationMemory(
            session_id=session_id,
            contact_id=contact_id,
            company=company,
            owner=owner,
            state=initial_state,
        )
        self._sessions[session_id] = memory
        self.append_event(
            memory,
            event_type="session_started",
            role="system",
            state=initial_state,
            text=f"Conversation session started for {company.business_name}.",
            metadata={"contact_id": contact_id},
        )
        return memory

    def get(self, session_id: str) -> ConversationMemory | None:
        """Return a session by ID if it is still held in memory."""

        return self._sessions.get(session_id)

    def append_event(
        self,
        memory: ConversationMemory,
        *,
        event_type: str,
        role: str,
        state: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        """Append a structured event to a conversation session."""

        event = ConversationEvent(
            id=str(uuid.uuid4()),
            session_id=memory.session_id,
            sequence=len(memory.events) + 1,
            event_type=event_type,
            role=role,
            state=state,
            text=text,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        memory.events.append(event)
        memory.updated_at = event.created_at
        return event

    def change_state(self, memory: ConversationMemory, next_state: str, *, reason: str) -> None:
        if memory.state == next_state:
            return
        previous_state = memory.state
        memory.state = next_state
        self.append_event(
            memory,
            event_type="state_changed",
            role="system",
            state=next_state,
            text=f"Conversation moved from {previous_state} to {next_state}.",
            metadata={"previous_state": previous_state, "next_state": next_state, "reason": reason},
        )

    def remember_need(self, memory: ConversationMemory, need: str) -> None:
        cleaned = need.strip()
        if cleaned and cleaned not in memory.discovered_needs:
            memory.discovered_needs.append(cleaned)

    def remember_objection(self, memory: ConversationMemory, objection: str) -> None:
        cleaned = objection.strip()
        if cleaned and cleaned not in memory.objections:
            memory.objections.append(cleaned)

    def remember_topic(self, memory: ConversationMemory, topic: str) -> None:
        cleaned = topic.strip()
        if cleaned and cleaned not in memory.quoted_topics:
            memory.quoted_topics.append(cleaned)

    def update_qualification(self, memory: ConversationMemory, values: dict[str, Any]) -> None:
        memory.qualification_notes.update(values)
        memory.updated_at = utc_now()


default_memory_manager = ConversationMemoryManager()
