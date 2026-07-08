"""Gemini 2.5 Flash reasoning provider for AI SDR calls."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ai_sdr.calling.interfaces import (
    AIReasoningContext,
    AIResponse,
    CallOutcome,
    LLMProvider,
    ProviderConfigurationError,
)
from ai_sdr.config import AISDRSettings


class GeminiLLMProvider(LLMProvider):
    """LLM provider that uses Google's Gemini API for live sales reasoning."""

    name = "gemini"

    def __init__(self, settings: AISDRSettings) -> None:
        self.settings = settings
        self._client: Any | None = None

    async def generate_next_response(self, context: AIReasoningContext) -> AIResponse:
        prompt = self._next_response_prompt(context)
        raw = await asyncio.to_thread(self._generate_json, prompt)
        return AIResponse(
            text=str(raw.get("text") or self._fallback_text(context)),
            current_goal=str(raw.get("current_goal") or "Keep the conversation useful and concise."),
            conversation_stage=str(raw.get("conversation_stage") or "Discovery"),
            detected_objection=str(raw.get("detected_objection") or "None detected"),
            customer_sentiment=str(raw.get("customer_sentiment") or "Neutral"),
            qualification_score=self._bounded_score(raw.get("qualification_score")),
            suggested_next_action=str(raw.get("suggested_next_action") or "Ask one focused follow-up question."),
            should_end_call=bool(raw.get("should_end_call") or False),
            metadata={"provider": self.name, "model": self.settings.gemini_model, "raw": raw},
        )

    async def summarize_call(self, context: AIReasoningContext) -> CallOutcome:
        prompt = self._summary_prompt(context)
        raw = await asyncio.to_thread(self._generate_json, prompt)
        return CallOutcome(
            conversation_summary=str(raw.get("conversation_summary") or self._fallback_summary(context)),
            qualification_score=self._bounded_score(raw.get("qualification_score")),
            interested=bool(raw.get("interested") or False),
            reason=str(raw.get("reason") or "Call completed without enough structured signal."),
            objections=self._string_list(raw.get("objections")),
            website_problems=self._string_list(raw.get("website_problems")),
            recommended_services=self._string_list(raw.get("recommended_services")),
            next_follow_up=str(raw.get("next_follow_up") or ""),
            metadata={"provider": self.name, "model": self.settings.gemini_model, "raw": raw},
        )

    def _generate_json(self, prompt: str) -> dict[str, Any]:
        if not self.settings.gemini_api_key:
            raise ProviderConfigurationError("Gemini provider requires GEMINI_API_KEY.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Gemini provider selected but the google-genai package is not installed."
            ) from exc

        if self._client is None:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)

        config: Any | None = None
        try:
            config = types.GenerateContentConfig(
                temperature=0.55,
                response_mime_type="application/json",
            )
        except Exception:
            config = None
        response = self._client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=config,
        )
        text = str(getattr(response, "text", "") or "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = self._extract_json_object(text)
        return parsed if isinstance(parsed, dict) else {}

    def _next_response_prompt(self, context: AIReasoningContext) -> str:
        transcript = self._transcript_text(context)
        interrupted = "The customer interrupted the previous AI response." if context.interrupted else ""
        return f"""
You are the LeadForge AI SDR on a live sales call. Sound like a professional human sales representative:
- natural, concise, consultative, and never robotic
- honest if asked whether you are AI
- one short response at a time
- reference relevant context only when it helps
- never mention Lead Generator or any lead generation module

Business: {context.business_name}
Owner/contact: {context.owner_name}
Industry: {context.industry}
City: {context.city}
Website: {context.website}
Objective: {context.objective}
{interrupted}

Transcript so far:
{transcript}

Return only JSON with:
{{
  "text": "next spoken sentence or two",
  "current_goal": "current goal",
  "conversation_stage": "Greeting | Permission | Discovery | Qualification | Website Discussion | AI Automation Discussion | Pricing | Objection Handling | Closing | Follow-up | Goodbye",
  "detected_objection": "objection or None detected",
  "customer_sentiment": "Positive | Interested | Engaged | Neutral | Concerned | Negative",
  "qualification_score": 0,
  "suggested_next_action": "operator-facing next action",
  "should_end_call": false
}}
"""

    def _summary_prompt(self, context: AIReasoningContext) -> str:
        return f"""
Summarize this completed LeadForge AI SDR phone call for CRM storage.
Use only the transcript and contact context. Do not invent facts.

Business: {context.business_name}
Owner/contact: {context.owner_name}
Industry: {context.industry}
City: {context.city}
Website: {context.website}
Objective: {context.objective}

Transcript:
{self._transcript_text(context)}

Return only JSON with:
{{
  "conversation_summary": "concise summary",
  "qualification_score": 0,
  "interested": false,
  "reason": "why interested or not interested",
  "objections": ["..."],
  "website_problems": ["..."],
  "recommended_services": ["..."],
  "next_follow_up": "specific follow-up recommendation or empty string"
}}
"""

    @staticmethod
    def _transcript_text(context: AIReasoningContext) -> str:
        if not context.transcript:
            return "No transcript lines yet."
        return "\n".join(f"{segment.role}: {segment.text}" for segment in context.transcript[-30:])

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _bounded_score(value: Any) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            score = 0
        return max(0, min(100, score))

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _fallback_text(context: AIReasoningContext) -> str:
        return (
            f"That makes sense. For {context.business_name}, what would make this worth "
            "a short follow-up with the owner?"
        )

    @staticmethod
    def _fallback_summary(context: AIReasoningContext) -> str:
        return f"AI SDR call completed for {context.business_name}."
