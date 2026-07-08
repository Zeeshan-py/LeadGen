"""Factory for assembling AI SDR calling provider stacks."""

from __future__ import annotations

from dataclasses import dataclass

from ai_sdr.calling.interfaces import LLMProvider, SpeechProvider, TelephonyProvider
from ai_sdr.calling.providers.cartesia_provider import CartesiaSpeechProvider
from ai_sdr.calling.providers.gemini_provider import GeminiLLMProvider
from ai_sdr.calling.providers.mock_provider import MockLLMProvider, MockSpeechProvider, MockTelephonyProvider
from ai_sdr.calling.providers.twilio_provider import TwilioTelephonyProvider
from ai_sdr.config import AISDRSettings


@dataclass(frozen=True)
class CallingProviderStack:
    """The three provider roles needed by one AI SDR call runtime."""

    telephony: TelephonyProvider
    llm: LLMProvider
    speech: SpeechProvider


def build_calling_provider_stack(settings: AISDRSettings) -> CallingProviderStack:
    """Build the configured provider stack.

    `AI_SDR_CALLING_MODE=mock` swaps all three providers for deterministic
    adapters. Otherwise each provider role can be replaced independently.
    """

    if settings.calling_mode == "mock":
        return CallingProviderStack(
            telephony=MockTelephonyProvider(),
            llm=MockLLMProvider(),
            speech=MockSpeechProvider(),
        )
    return CallingProviderStack(
        telephony=_telephony_provider(settings),
        llm=_llm_provider(settings),
        speech=_speech_provider(settings),
    )


def _telephony_provider(settings: AISDRSettings) -> TelephonyProvider:
    if settings.telephony_provider == "twilio":
        return TwilioTelephonyProvider(settings)
    if settings.telephony_provider == "mock":
        return MockTelephonyProvider()
    raise ValueError(f"Unsupported AI SDR telephony provider: {settings.telephony_provider}")


def _llm_provider(settings: AISDRSettings) -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiLLMProvider(settings)
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    raise ValueError(f"Unsupported AI SDR LLM provider: {settings.llm_provider}")


def _speech_provider(settings: AISDRSettings) -> SpeechProvider:
    if settings.speech_provider == "cartesia":
        return CartesiaSpeechProvider(settings)
    if settings.speech_provider == "mock":
        return MockSpeechProvider()
    raise ValueError(f"Unsupported AI SDR speech provider: {settings.speech_provider}")
