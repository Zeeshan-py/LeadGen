"""Prompt construction for the production AI SDR call brain."""

from __future__ import annotations

import json
from typing import Any

from ai_sdr.calling.interfaces import AIReasoningContext, TranscriptSegment
from ai_sdr.conversation.memory_extractor import ExtractedFacts, SalesMemoryExtractor


class PromptBuilder:
    """Builds concise, memory-aware prompts for live SDR turns."""

    def __init__(self, *, memory_extractor: SalesMemoryExtractor | None = None) -> None:
        self.memory_extractor = memory_extractor or SalesMemoryExtractor()

    def next_response_prompt(self, context: AIReasoningContext) -> str:
        facts = self._facts_for_context(context)
        transcript = self._transcript_text(context.transcript)
        interrupted = (
            "The customer interrupted the previous answer. Acknowledge briefly and continue listening."
            if context.interrupted
            else "No interruption on the last turn."
        )
        return f"""
You are the LeadForge AI SDR on a live phone call.

Non-negotiable speaking rules:
- Reply in 1 to 3 sentences and 40 spoken words or fewer.
- Ask one focused question at a time.
- Use a calm, professional SDR tone. No markdown, lists, stage labels, or filler.
- For website offers, follow this exact flow:
  confirm you reached the business, mention you found them on Google Maps and no proper website was listed, give one website benefit, mention LeadForge has built modern 3D website projects, ask if they are interested, then collect WhatsApp/email.
- Do not ask how customers contact them unless the user objective specifically asks that question.
- Do not repeat questions already answered in memory.
- Preserve exact names, phone numbers, emails, addresses, URLs, budgets, times, and dates.
- If a value is uncertain, verify it before using it.
- If asked whether you are AI, answer honestly and briefly.
- If the customer objects, acknowledge it first, then ask a low-pressure next question.
- Do not invent prices, discounts, guarantees, services, or claims outside the objective.

Business context:
{json.dumps(self._business_context(context), ensure_ascii=True, indent=2)}

Remembered customer facts:
{json.dumps(facts, ensure_ascii=True, indent=2)}

Interruption context: {interrupted}

Recent transcript:
{transcript}

Return only JSON with:
{{
  "text": "the exact next spoken reply",
  "current_goal": "current goal",
  "conversation_stage": "Greeting | Permission | Discovery | Qualification | Website Discussion | AI Automation Discussion | Pricing | Objection Handling | Closing | Follow-up | Goodbye",
  "detected_objection": "objection or None detected",
  "customer_sentiment": "Positive | Interested | Engaged | Neutral | Concerned | Negative",
  "qualification_score": 0,
  "suggested_next_action": "operator-facing next action",
  "should_end_call": false
}}
"""

    @staticmethod
    def _business_context(context: AIReasoningContext) -> dict[str, Any]:
        return {
            "business_name": context.business_name,
            "owner_name": context.owner_name,
            "industry": context.industry,
            "city": context.city,
            "website": context.website or "No website recorded",
            "objective": context.objective,
            "crm": context.memory,
        }

    def _facts_for_context(self, context: AIReasoningContext) -> dict[str, Any]:
        stored = context.memory.get("facts") if isinstance(context.memory, dict) else None
        aggregate = ExtractedFacts()
        if isinstance(stored, dict):
            aggregate = self._facts_from_dict(stored)
        for segment in context.transcript:
            if segment.role == "customer":
                aggregate.merge(self.memory_extractor.extract(segment.text))
        return aggregate.to_dict()

    @staticmethod
    def _facts_from_dict(values: dict[str, Any]) -> ExtractedFacts:
        facts = ExtractedFacts()
        for key, value in values.items():
            if hasattr(facts, key):
                setattr(facts, key, value)
        return facts

    @staticmethod
    def _transcript_text(transcript: list[TranscriptSegment]) -> str:
        if not transcript:
            return "No transcript lines yet."
        return "\n".join(
            f"{segment.role}{' partial' if not segment.is_final else ''}: {segment.text}"
            for segment in transcript[-30:]
        )
