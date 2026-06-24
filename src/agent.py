"""The single agent entry point.

Both the batch runner and the FastAPI service import `run_agent` from here, so
there is exactly one code path. Dependencies (LLM provider + repository) and the
compiled graph are built once per process and reused.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional, Union

from .config import Settings, get_settings
from .data_layer import get_repository
from .graph import build_graph
from .llm import get_llm
from .models import AgentState, Inquiry, LeadBrief
from .nodes import Deps


@lru_cache(maxsize=1)
def _runtime():
    """Build deps + compiled graph once. Cached for the process lifetime."""
    settings: Settings = get_settings()
    deps = Deps(llm=get_llm(settings), repo=get_repository(settings), settings=settings)
    graph = build_graph(deps)
    return settings, deps, graph


def runtime_info() -> dict:
    settings, deps, _ = _runtime()
    return {
        "llm_provider": deps.llm.name,
        "matcher_backend": type(deps.repo).__name__,
        "listings_loaded": deps.repo.count(),
    }


def run_agent(
    inquiry: Union[Inquiry, dict],
    persist: bool = False,
    out_dir: Optional[str] = None,
) -> LeadBrief:
    """Run the full LangGraph agent over one inquiry and return its LeadBrief."""
    _, _, graph = _runtime()
    if isinstance(inquiry, dict):
        inquiry = Inquiry(**inquiry)

    state = AgentState(inquiry=inquiry, persist=persist, out_dir=out_dir)
    result = graph.invoke(state)

    # LangGraph returns the final channel values; brief is a LeadBrief instance.
    brief = result["brief"] if isinstance(result, dict) else result.brief
    if isinstance(brief, dict):  # safety net across langgraph versions
        brief = LeadBrief(**brief)
    return brief
