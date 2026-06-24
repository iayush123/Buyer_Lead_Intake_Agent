"""Node 6 - Persist outputs to files.

Writes <lead_id>.md and <lead_id>.json for the brief. Gated on state.persist so
the SAME graph can be used by the API (which returns JSON and writes nothing) and
by the batch runner (which sets persist=True and an out_dir). This is how the API
and batch share one agent code path.
"""
from __future__ import annotations

import json
import os

from ..models import AgentState
from ..render import brief_to_markdown
from .deps import Deps


def make_persist_node(deps: Deps):
    def persist(state: AgentState) -> dict:
        if not state.persist or not state.brief:
            state.log("persist", "skipped (persist disabled or no brief)")
            return {"trace": state.trace}

        out_dir = state.out_dir or deps.settings.output_dir
        os.makedirs(out_dir, exist_ok=True)
        lead_id = state.brief.lead_id

        md_path = os.path.join(out_dir, f"{lead_id}.md")
        json_path = os.path.join(out_dir, f"{lead_id}.json")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(brief_to_markdown(state.brief))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(state.brief.model_dump(), f, indent=2, default=str)

        state.log("persist", f"wrote {md_path} + {json_path}")
        return {"trace": state.trace}

    return persist
