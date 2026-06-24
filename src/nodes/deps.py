"""Dependencies injected into every node (LLM provider, data repository,
settings). Built once in agent.py and closed over by the node factories, so the
graph nodes stay pure functions of (state) -> updates."""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..data_layer.base import ListingRepository
from ..llm.base import LLMProvider


@dataclass
class Deps:
    llm: LLMProvider
    repo: ListingRepository
    settings: Settings
