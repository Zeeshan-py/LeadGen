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
                f"Based on what you shared, I think a focused review for {business} would be worth the time. "
                "Would tomorrow afternoon or the next morning be easier for a 15-minute look at the website and follow-up flow?"
            )
        return (
            f"It sounds like there may be something useful here for {business}, but I would want to understand one more piece first. "
            "What would make this worth a short follow-up conversation for you?"
        )

    def follow_up_prompt(self, memory: ConversationMemory) -> str:
        channel = "email" if memory.owner.email else "a short note"
        return (
            f"I will keep it practical and send {channel} with the main points for {memory.company.business_name}. "
            "If it looks relevant, we can turn that into a quick review instead of a long sales call."
        )

    def goodbye(self, memory: ConversationMemory) -> str:
        return (
            f"Thanks for the time. I appreciate it, and I hope the next few weeks go well for {memory.company.business_name}."
        )
