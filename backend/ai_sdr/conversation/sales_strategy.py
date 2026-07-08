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
        previous_line = f" I also saw the note that {previous.lower()}" if previous else ""
        return (
            f"Hi {owner.display_name}, this is Ava with LeadForge. I was looking at {company.business_name}, "
            f"especially the {company.industry_phrase} work you do{location}.{previous_line} "
            "Did I catch you with half a minute?"
        )

    def permission_reply(self, memory: ConversationMemory) -> str:
        context = memory.company.website_reference()
        return (
            f"Thanks. I will keep it brief. {context} "
            "I am trying to understand whether there is a practical way to help more interested visitors turn into real conversations."
        )

    def discovery_reply(self, memory: ConversationMemory, customer_message: str) -> str:
        need = self._summarize_need(customer_message)
        if need:
            return (
                f"That makes sense. If {memory.company.business_name} is already seeing {need}, "
                "the important question is where the process is leaking: the website, the follow-up, or the booking step."
            )
        return (
            f"Got it. For a {memory.company.industry_phrase} business like {memory.company.business_name}, "
            "I usually look for one simple gap: are people finding you but not taking the next step?"
        )

    def website_discussion(self, memory: ConversationMemory) -> str:
        website = memory.company.website
        if website:
            return (
                f"Looking at {website}, I would focus less on making it prettier and more on whether each page gives a clear next step. "
                "A small conversion gap can matter if the traffic is already there."
            )
        return (
            "Since I do not have a website recorded, I would first confirm your main online presence and then look at whether people "
            "have an easy path to contact you."
        )

    def automation_discussion(self, memory: ConversationMemory) -> str:
        return (
            "The automation side is usually simple: respond quickly, route the right inquiries, and follow up without making your team "
            "babysit every lead. The point is not to replace judgment; it is to keep good opportunities from going quiet."
        )

    def pricing_discussion(self, memory: ConversationMemory) -> str:
        return (
            "On pricing, I would rather anchor it to the actual opportunity than toss out a generic package. "
            f"If {memory.company.business_name} is losing even a few good inquiries a month, the math is different than if everything is already tight."
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
