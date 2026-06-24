"""OpenAI-backed provider. Thin wrapper: it only does LANGUAGE work
(extraction + composition) and returns parsed JSON. Falls back to the mock's
parser if the API/JSON ever fails, so the pipeline never hard-crashes."""
from __future__ import annotations

import json
from typing import Any

from .base import LLMProvider
from .mock_provider import MockProvider
from .prompts import (
    COMPOSE_SYSTEM,
    EXTRACT_SYSTEM,
    build_compose_user,
    build_extract_user,
)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI  # imported lazily so the dep is optional

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self._fallback = MockProvider()

    def _chat_json(self, system: str, user: str) -> dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    def extract(self, message: str) -> dict[str, Any]:
        try:
            data = self._chat_json(EXTRACT_SYSTEM, build_extract_user(message))
            # backfill any missing keys with the deterministic parser
            base = self._fallback.extract(message)
            base.update({k: v for k, v in data.items() if v is not None})
            return base
        except Exception:
            return self._fallback.extract(message)

    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._chat_json(COMPOSE_SYSTEM, build_compose_user(payload))
        except Exception:
            return self._fallback.compose(payload)
