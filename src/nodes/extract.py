"""Node 2 - Extract structured requirements (the LANGUAGE step).

This is the only place the inquiry text is interpreted as meaning. It calls the
LLM provider's extract() and validates the result into a typed BuyerProfile.
Everything downstream works off the typed profile, not the raw text.
"""
from __future__ import annotations

from ..models import AgentState, BuyerProfile, BuyerType
from .deps import Deps


def make_extract_node(deps: Deps):
    def extract(state: AgentState) -> dict:
        raw = deps.llm.extract(state.inquiry.message)

        # coerce buyer_type safely
        bt = raw.get("buyer_type")
        try:
            BuyerType(bt)
        except (ValueError, TypeError):
            raw["buyer_type"] = BuyerType.unknown.value

        profile = BuyerProfile(**{k: raw.get(k) for k in BuyerProfile.model_fields if k in raw})
        state.profile = profile
        state.log("extract", f"provider={deps.llm.name} type={profile.buyer_type} "
                            f"beds={profile.min_beds} budget={profile.budget} "
                            f"locs={profile.locations} vague={profile.is_too_vague_to_match} "
                            f"human={profile.requires_human_judgment}")
        return {"profile": profile, "trace": state.trace}

    return extract
