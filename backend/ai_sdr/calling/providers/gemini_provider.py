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
from ai_sdr.conversation.prompt_builder import PromptBuilder
from ai_sdr.conversation.response_validator import ResponseValidator


class GeminiLLMProvider(LLMProvider):
    """LLM provider that uses Google's Gemini API for live sales reasoning."""

    name = "gemini"

    def __init__(self, settings: AISDRSettings) -> None:
        self.settings = settings
        self._client: Any | None = None
        self.prompt_builder = PromptBuilder()
        self.response_validator = ResponseValidator()

    async def generate_next_response(self, context: AIReasoningContext) -> AIResponse:
        prompt = self._next_response_prompt(context)
        raw = await asyncio.to_thread(self._generate_json, prompt)
        text = self.response_validator.validate(
            str(raw.get("text") or self._fallback_text(context)),
            fallback=self._fallback_text(context),
        )
        return AIResponse(
            text=text,
            current_goal=str(raw.get("current_goal") or "Keep the conversation useful and concise."),
            conversation_stage=str(raw.get("conversation_stage") or "Discovery"),
            detected_objection=str(raw.get("detected_objection") or "None detected"),
            customer_sentiment=str(raw.get("customer_sentiment") or "Neutral"),
            qualification_score=self._bounded_score(raw.get("qualification_score")),
            suggested_next_action=str(raw.get("suggested_next_action") or "Ask one focused follow-up question."),
            should_end_call=self._bool_value(raw.get("should_end_call")),
            metadata={
                "provider": self.name,
                "model": self.settings.gemini_model,
                "raw": raw,
                "spoken_word_count": self.response_validator.word_count(text),
            },
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
        text = self._generate_text(prompt, config)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = self._extract_json_object(text)
        return parsed if isinstance(parsed, dict) else {}

    def _generate_text(self, prompt: str, config: Any | None) -> str:
        assert self._client is not None
        try:
            stream = self._client.models.generate_content_stream(
                model=self.settings.gemini_model,
                contents=prompt,
                config=config,
            )
        except (AttributeError, TypeError):
            stream = None
        if stream is not None:
            try:
                return "".join(str(getattr(chunk, "text", "") or "") for chunk in stream)
            except Exception:
                # Some Gemini configurations can reject streaming JSON. Fall back
                # to normal generation instead of letting the live call go silent.
                pass
        response = self._client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=config,
        )
        return str(getattr(response, "text", "") or "")

    def _next_response_prompt(self, context: AIReasoningContext) -> str:
        return self.prompt_builder.next_response_prompt(context)

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
    def _bool_value(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "yes", "1"}
        return bool(value)

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _fallback_text(context: AIReasoningContext) -> str:
        return f"That makes sense. For {context.business_name}, what would make a short follow-up worth your time?"

    @staticmethod
    def _fallback_summary(context: AIReasoningContext) -> str:
        return f"AI SDR call completed for {context.business_name}."
