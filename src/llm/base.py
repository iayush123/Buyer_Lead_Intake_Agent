"""LLM provider interface.

The agent only ever talks to the LLM through these two *semantic* operations.
That keeps the provider swappable (OpenAI / Anthropic / deterministic mock) and
keeps the LLM's job tightly scoped to LANGUAGE work:

  * extract()  -> turn messy free text into a structured BuyerProfile dict
  * compose()  -> turn the (already computed) profile + matches into prose

No matching, scoring, or filtering ever happens in the LLM - that is the data
layer's job. See README "Why this boundary".
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, message: str) -> dict[str, Any]:
        """Return a dict matching the BuyerProfile schema (best-effort)."""
        raise NotImplementedError

    @abstractmethod
    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a dict with keys:
            buyer_summary: str
            property_reasons: dict[listing_id -> reason str]
            things_to_be_aware_of: list[str]
            suggested_next_action: str
        """
        raise NotImplementedError
