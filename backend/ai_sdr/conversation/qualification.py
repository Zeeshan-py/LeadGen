"""Qualification scoring and discovery question strategy for AI SDR."""

from __future__ import annotations

from dataclasses import dataclass

from ai_sdr.conversation.memory_manager import ConversationMemory


NEED_KEYWORDS = {
    "lead flow": ("lead", "leads", "inquiries", "customers", "traffic"),
    "booking friction": ("booking", "appointment", "schedule", "form", "calls"),
    "automation fit": ("follow up", "follow-up", "manual", "admin", "automation", "reply"),
    "urgency": ("soon", "this month", "quarter", "urgent", "need", "problem"),
    "authority": ("owner", "decision", "i decide", "my team", "partner"),
}


@dataclass(frozen=True)
class QualificationResult:
    """Outcome of evaluating a conversation for fit and sales readiness."""

    score: int
    signals: list[str]
    missing: list[str]
    is_qualified: bool

    def to_dict(self) -> dict[str, object]:
        """Serialize qualification fields for events and API responses."""

        return {
            "score": self.score,
            "signals": self.signals,
            "missing": self.missing,
            "is_qualified": self.is_qualified,
        }


class QualificationEngine:
    """Scores conversation fit from customer language and remembered context."""

    def evaluate(self, memory: ConversationMemory, latest_message: str = "") -> QualificationResult:
        text = " ".join(
            [
                latest_message,
                " ".join(memory.discovered_needs),
                " ".join(event.text for event in memory.events if event.role == "customer"),
            ]
        ).lower()
        signals = [
            signal
            for signal, keywords in NEED_KEYWORDS.items()
            if any(keyword in text for keyword in keywords)
        ]
        if memory.company.website:
            signals.append("website present")
        if memory.owner.name:
            signals.append("known decision contact")
        score = min(95, 20 + (len(set(signals)) * 12) + (len(memory.discovered_needs) * 6))
        missing = [
            label
            for label in ("lead flow", "booking friction", "urgency", "authority")
            if label not in signals
        ]
        return QualificationResult(
            score=score,
            signals=sorted(set(signals)),
            missing=missing,
            is_qualified=score >= 68 and len(missing) <= 2,
        )

    def discovery_question(self, memory: ConversationMemory) -> str:
        business = memory.company.business_name
        if memory.company.website:
            return (
                f"When people find {business} online, what should they do next: "
                "call, book, request a quote, or something else?"
            )
        return (
            f"For {business}, where do most new conversations come from now: referrals, search, "
            "social, or repeat customers?"
        )

    def qualification_question(self, memory: ConversationMemory) -> str:
        missing = set(memory.qualification_notes.get("missing", []))
        if "urgency" in missing:
            return "How soon would improving that process matter: this month, this quarter, or later?"
        if "authority" in missing:
            return f"Are you the person who would decide whether {memory.company.business_name} tries this?"
        return "If that improved, what would matter most: more bookings, less admin time, or better lead quality?"
