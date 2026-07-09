"""Closing, follow-up, and goodbye language for AI SDR conversations."""

from __future__ import annotations

from ai_sdr.conversation.memory_manager import ConversationMemory
from ai_sdr.conversation.qualification import QualificationResult


class ClosingStrategy:
    """Generates close, follow-up, and goodbye language."""

    def next_step_prompt(self, memory: ConversationMemory, qualification: QualificationResult) -> str:
        business = memory.company.business_name
        if qualification.is_qualified:
            return (
                f"A focused review for {business} sounds worth it. "
                "Would tomorrow afternoon or the next morning suit a 15-minute look?"
            )
        return (
            f"There may be something useful for {business}. "
            "What would make a short follow-up worth your time?"
        )

    def follow_up_prompt(self, memory: ConversationMemory) -> str:
        channel = "email" if memory.owner.email else "a short note"
        return (
            f"I will send {channel} with the practical points for {memory.company.business_name}. "
            "If it looks relevant, we can make it a quick review."
        )

    def goodbye(self, memory: ConversationMemory) -> str:
        return (
            f"Thanks for the time. I appreciate it, and I hope the next few weeks go well for {memory.company.business_name}."
        )
