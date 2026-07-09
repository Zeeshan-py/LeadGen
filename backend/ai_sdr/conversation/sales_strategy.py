"""Natural sales-language strategy for AI SDR responses."""

from __future__ import annotations

from ai_sdr.conversation.company_information import CompanyInformation
from ai_sdr.conversation.memory_manager import ConversationMemory
from ai_sdr.conversation.owner_information import OwnerInformation


class SalesStrategy:
    """Professional SDR wording that stays specific without pretending to be human."""

    def greeting(self, company: CompanyInformation, owner: OwnerInformation) -> str:
        location = f" in {company.location_phrase}" if company.location_phrase else ""
        previous = company.previous_interaction_reference()
        previous_line = f", and that {previous.lower()}" if previous else ""
        return (
            f"Hi {owner.display_name}, Ava with LeadForge. I saw {company.business_name}, "
            f"the {company.industry_phrase} work{location}{previous_line}. "
            "Did I catch you with half a minute?"
        )

    def permission_reply(self, memory: ConversationMemory) -> str:
        return (
            f"Thanks. For {memory.company.business_name}, I'll keep this practical and focus on whether "
            "visitors can become real enquiries."
        )

    def discovery_reply(self, memory: ConversationMemory, customer_message: str) -> str:
        need = self._summarize_need(customer_message)
        if need:
            return (
                f"That makes sense. If {memory.company.business_name} is seeing {need}, "
                "we should find the exact step that leaks."
            )
        return (
            f"Got it. For {memory.company.business_name}, I am listening for one gap: "
            "people finding you but not taking the next step."
        )

    def website_discussion(self, memory: ConversationMemory) -> str:
        website = memory.company.website
        if website:
            return (
                f"With {website}, I would check whether every page gives a clear next step, "
                "not just whether it looks polished."
            )
        return (
            "Since no website is recorded, I would first confirm where people see you online "
            "and whether contacting you feels easy."
        )

    def automation_discussion(self, memory: ConversationMemory) -> str:
        return (
            "The automation piece is simple: reply quickly, route serious enquiries, and stop good opportunities "
            "from going quiet."
        )

    def pricing_discussion(self, memory: ConversationMemory) -> str:
        return (
            "Pricing depends on the pages, 3D work, and follow-up needed. "
            f"For {memory.company.business_name}, I would price it after seeing the real conversion gap."
        )

    def bridge_to_question(self, statement: str, question: str) -> str:
        return f"{statement} {question}"

    @staticmethod
    def _summarize_need(message: str) -> str:
        text = message.lower()
        if any(token in text for token in ("booking", "appointment", "schedule")):
            return "booking friction"
        if any(token in text for token in ("lead", "inquiry", "customer", "traffic")):
            return "lead flow pressure"
        if any(token in text for token in ("follow", "admin", "manual", "reply")):
            return "manual follow-up work"
        return ""
