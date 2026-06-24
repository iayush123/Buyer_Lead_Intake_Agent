"""Anthropic-backed provider. Same contract as the others; only does language
work and falls back to the deterministic parser on any failure."""
from __future__ import annotations

import json
import re
from typing import Any

from .base import LLMProvider
from .mock_provider import MockProvider
from .prompts import (
    COMPOSE_SYSTEM,
    EXTRACT_SYSTEM,
    build_compose_user,
    build_extract_user,
)


def _first_json(text: str) -> dict[str, Any]:
    # Claude sometimes wraps JSON in prose; grab the first {...} block.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0) if m else text)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest") -> None:
        import anthropic  # lazy import

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self._fallback = MockProvider()

    def _message_json(self, system: str, user: str) -> dict[str, Any]:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _first_json(resp.content[0].text)

    def extract(self, message: str) -> dict[str, Any]:
        try:
            data = self._message_json(EXTRACT_SYSTEM, build_extract_user(message))
            base = self._fallback.extract(message)
            base.update({k: v for k, v in data.items() if v is not None})
            return base
        except Exception:
            return self._fallback.extract(message)

    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._message_json(COMPOSE_SYSTEM, build_compose_user(payload))
        except Exception:
            return self._fallback.compose(payload)
