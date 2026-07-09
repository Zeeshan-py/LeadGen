"""Objection detection and response templates for AI SDR conversations."""

from __future__ import annotations

from dataclasses import dataclass

from ai_sdr.conversation.memory_manager import ConversationMemory


@dataclass(frozen=True)
class ObjectionResult:
    """Detected objection metadata and recommended response."""

    code: str
    label: str
    severity: str
    reply: str

    @property
    def detected(self) -> bool:
        return bool(self.code)

    def to_dict(self) -> dict[str, str | bool]:
        """Serialize objection data for structured conversation events."""

        return {
            "detected": self.detected,
            "code": self.code,
            "label": self.label,
            "severity": self.severity,
            "reply": self.reply,
        }


class ObjectionHandler:
    """Detects common sales objections and produces respectful responses."""

    def detect(self, message: str, memory: ConversationMemory) -> ObjectionResult:
        text = message.lower()
        if self._asked_ai_identity(text):
            return ObjectionResult(
                code="ai_identity",
                label="Asked if AI",
                severity="low",
                reply=(
                    f"Yes, I am an AI assistant for LeadForge. I am calling about {memory.company.business_name} "
                    "to see if a short website review is useful, and you can ask me to stop."
                ),
            )
        if any(token in text for token in ("not interested", "no interest", "don't need", "do not need")):
            return ObjectionResult(
                code="not_interested",
                label="Not interested",
                severity="medium",
                reply=(
                    "That is completely fair. Is it already handled, or is improving the website "
                    "not a priority right now?"
                ),
            )
        if any(token in text for token in ("busy", "bad time", "meeting", "later", "call me back")):
            return ObjectionResult(
                code="busy",
                label="Busy right now",
                severity="low",
                reply=(
                    "No problem. Should I send a quick note, or follow up another day when you have more room?"
                ),
            )
        if any(token in text for token in ("cost", "price", "pricing", "expensive", "budget")):
            return ObjectionResult(
                code="pricing",
                label="Pricing concern",
                severity="medium",
                reply=(
                    "Pricing depends on the pages, 3D work, and follow-up needed. "
                    f"For {memory.company.business_name}, I would first check the conversion gap, then quote properly."
                ),
            )
        if any(token in text for token in ("send info", "email me", "send me", "information")):
            return ObjectionResult(
                code="send_information",
                label="Requests information",
                severity="low",
                reply=(
                    "I can do that. Should the note focus on website conversion, missed follow-up, "
                    "booking, or lead quality?"
                ),
            )
        return ObjectionResult(code="", label="", severity="", reply="")

    @staticmethod
    def _asked_ai_identity(text: str) -> bool:
        compact = " ".join(text.replace("?", " ").split())
        return any(
            phrase in compact
            for phrase in (
                "are you ai",
                "are you an ai",
                "are you a bot",
                "are you human",
                "is this ai",
                "is this an ai",
            )
        )
