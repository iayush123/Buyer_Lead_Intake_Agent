"""Node 1 - Ingest.

Normalizes the raw inquiry. Trivial today, but it's the seam where, in
production, you'd attach channel-specific cleanup (email signature stripping,
HTML unescaping, dedupe against prior leads) without touching the rest of the
graph.
"""
from __future__ import annotations

from ..models import AgentState
from .deps import Deps


def make_ingest_node(deps: Deps):
    def ingest(state: AgentState) -> dict:
        msg = (state.inquiry.message or "").strip()
        state.inquiry.message = msg
        state.log("ingest", f"lead={state.inquiry.lead_id} channel={state.inquiry.channel} "
                            f"chars={len(msg)}")
        return {"inquiry": state.inquiry, "trace": state.trace}

    return ingest
