"""The LangGraph state graph - THIS is the agent design.

Six explicit nodes, one per step, sharing one typed AgentState. The ordering
encodes the core principle: understand language (extract) -> guard the boundary
(safety) -> do data work deterministically (match) -> turn it back into language
(compose) -> side effects (persist).

           ┌────────┐   ┌─────────┐   ┌────────┐   ┌───────┐   ┌─────────┐   ┌─────────┐
  START -> │ ingest │ ->│ extract │ ->│ safety │ ->│ match │ ->│ compose │ ->│ persist │ -> END
           └────────┘   └─────────┘   └────────┘   └───────┘   └─────────┘   └─────────┘
            (clean)      LLM (lang)    determ.      determ.     LLM (lang)    determ. (gated)

The LLM is used in exactly TWO nodes (extract, compose); everything that decides
what the realtor sees - matching, ranking, flags, next action, confidence - is
deterministic code.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .models import AgentState
from .nodes import (
    Deps,
    make_compose_node,
    make_extract_node,
    make_ingest_node,
    make_match_node,
    make_persist_node,
    make_safety_node,
)


def build_graph(deps: Deps):
    g = StateGraph(AgentState)

    g.add_node("ingest", make_ingest_node(deps))
    g.add_node("extract", make_extract_node(deps))
    g.add_node("safety", make_safety_node(deps))
    g.add_node("match", make_match_node(deps))
    g.add_node("compose", make_compose_node(deps))
    g.add_node("persist", make_persist_node(deps))

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "extract")
    g.add_edge("extract", "safety")
    g.add_edge("safety", "match")
    g.add_edge("match", "compose")
    g.add_edge("compose", "persist")
    g.add_edge("persist", END)

    return g.compile()
