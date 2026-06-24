"""LLM provider factory. Chooses the provider from settings, with a safe
fallback to the deterministic mock so the agent always runs."""
from __future__ import annotations

from ..config import Settings
from .base import LLMProvider
from .mock_provider import MockProvider


def get_llm(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider

    try:
        if provider == "openai" and settings.openai_api_key:
            from .openai_provider import OpenAIProvider

            return OpenAIProvider(settings.openai_api_key, settings.openai_model)

        if provider == "anthropic" and settings.anthropic_api_key:
            from .anthropic_provider import AnthropicProvider

            return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    except Exception as exc:  # SDK not installed / init failure -> stay runnable
        print(f"[llm] provider '{provider}' unavailable ({exc}); using deterministic mock.")

    # default / fallback - fully offline, no key required
    return MockProvider()


__all__ = ["get_llm", "LLMProvider", "MockProvider"]
