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
                    "Yes, I am an AI assistant for LeadForge, not a human pretending otherwise. "
                    f"I am using the information we have about {memory.company.business_name} to see whether a short website "
                    "and automation review would be useful. You can ask me to stop at any point."
                ),
            )
        if any(token in text for token in ("not interested", "no interest", "don't need", "do not need")):
            return ObjectionResult(
                code="not_interested",
                label="Not interested",
                severity="medium",
                reply=(
                    "That is completely fair. Before I let you go, is that because this is already handled, "
                    "or because improving the website and follow-up process is not a priority right now?"
                ),
            )
        if any(token in text for token in ("busy", "bad time", "meeting", "later", "call me back")):
            return ObjectionResult(
                code="busy",
                label="Busy right now",
                severity="low",
                reply=(
                    "No problem. I can keep it simple: would it be better to send a quick note, or should I follow up "
                    "another day when you have a little more room?"
                ),
            )
        if any(token in text for token in ("cost", "price", "pricing", "expensive", "budget")):
            return ObjectionResult(
                code="pricing",
                label="Pricing concern",
                severity="medium",
                reply=(
                    "Totally reasonable to ask. Pricing depends on the workflow, so I would not want to throw out a random number. "
                    f"The useful first step is a short review of {memory.company.business_name}'s current conversion and follow-up gaps, "
                    "then you can decide whether the economics make sense."
                ),
            )
        if any(token in text for token in ("send info", "email me", "send me", "information")):
            return ObjectionResult(
                code="send_information",
                label="Requests information",
                severity="low",
                reply=(
                    "I can do that. To make it relevant instead of generic, what should I focus the note on: "
                    "website conversion, missed follow-ups, booking automation, or lead quality?"
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
