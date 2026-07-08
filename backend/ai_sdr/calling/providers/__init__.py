"""Concrete AI SDR calling provider implementations."""

from ai_sdr.calling.providers.factory import CallingProviderStack, build_calling_provider_stack

__all__ = ["CallingProviderStack", "build_calling_provider_stack"]
