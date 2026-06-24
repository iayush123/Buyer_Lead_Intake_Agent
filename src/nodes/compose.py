"""Node 5 - Compose the Lead Brief.

The LLM writes the *prose* (buyer summary + per-property reasons). Everything
decision-bearing - the next action, the confidence rating, which concerns to
surface, the security flag - is assembled deterministically in this node so it
can't be hallucinated. This keeps the language/judgement boundary crisp.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import AgentState, LeadBrief
from .deps import Deps


def _confidence(state: AgentState) -> tuple[str, list[str]]:
    p = state.profile
    notes: list[str] = []
    matches = state.matches

    if p.is_too_vague_to_match:
        notes.append("Lead too vague to match; confidence low until qualified.")
        return "low", notes
    if not matches:
        notes.append("No inventory matched the hard constraints.")
        return "low", notes

    in_budget_active = [m for m in matches if m.fits_in_budget and m.listing_status == "Active"]
    if p.requires_human_judgment:
        notes.append("Contains a question requiring realtor judgment (e.g. negotiation / "
                     "seller motivation); brief gives context only.")
    if not p.budget:
        notes.append("Budget not stated; matches are size/location-based only.")
    if any(m.fits_in_stretch_only for m in matches):
        notes.append("Some matches rely on the stretch budget.")
    if p.special_needs:
        notes.append("Buyer has wants not in the MLS feed (e.g. "
                     f"{', '.join(p.special_needs[:3])}); verify manually.")

    if len(in_budget_active) >= 3 and not p.requires_human_judgment and not p.special_needs:
        return "high", notes or ["Strong, in-budget, active matches on all hard criteria."]
    return "medium", notes or ["Reasonable matches with minor caveats."]


def _next_action(state: AgentState) -> str:
    p = state.profile
    buyer = state.inquiry.buyer_name or "the buyer"
    if state.security_flag.triggered:
        # still a real lead - act on the genuine request, note the security event
        pass
    if p.is_too_vague_to_match:
        return (f"Call {buyer} for a 10-minute qualifying conversation to pin down budget, "
                f"target neighborhoods, size and goals before sending any listings.")
    if p.requires_human_judgment:
        return (f"Call {buyer} personally. Provide factual listing context but do NOT quote an "
                f"offer number or speculate on seller motivation over email - advise on "
                f"price/strategy live, as the licensed agent.")
    if not state.matches:
        return (f"Call {buyer} to recalibrate budget/criteria; set up a saved search + alert so "
                f"they're notified the moment matching inventory comes on.")
    if all(m.fits_in_stretch_only for m in state.matches):
        return (f"Call {buyer} to confirm the stretch budget is real, then schedule showings for "
                f"the top matches (all sit just above the base budget).")
    n = len(state.matches)
    return (f"Call {buyer} within 24h to confirm priorities and schedule showings for the top "
            f"{n} match{'es' if n != 1 else ''}; flag any 'Pending'/'Under Contract' status first.")


def make_compose_node(deps: Deps):
    def compose(state: AgentState) -> dict:
        p = state.profile
        payload = {
            "buyer_name": state.inquiry.buyer_name,
            "profile": p.model_dump(),
            "matches": [m.model_dump() for m in state.matches],
            "concerns": state.data_concerns,
        }
        prose = deps.llm.compose(payload)

        # apply LLM prose reasons to each match (fall back to deterministic reasons)
        reasons_map = prose.get("property_reasons") or {}
        for m in state.matches:
            r = reasons_map.get(m.listing_id)
            if r:
                m.reasons = [r]

        # things to be aware of: deterministic concerns + per-match caveats + any LLM extras
        aware: list[str] = list(state.data_concerns)
        for m in state.matches:
            for c in m.caveats:
                aware.append(f"{m.address}: {c}")
        for extra in (prose.get("things_to_be_aware_of") or []):
            aware.append(extra)
        if state.security_flag.triggered:
            aware.insert(0, "SECURITY: " + (state.security_flag.detail or "Embedded instruction ignored."))

        confidence, conf_notes = _confidence(state)

        brief = LeadBrief(
            lead_id=state.inquiry.lead_id,
            buyer_name=state.inquiry.buyer_name,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            buyer_summary=prose.get("buyer_summary") or "",
            recommended_properties=state.matches,
            things_to_be_aware_of=_dedupe(aware),
            suggested_next_action=_next_action(state),
            confidence=confidence,
            confidence_notes=conf_notes,
            security_flag=state.security_flag,
            buyer_profile=p,
        )
        state.brief = brief
        state.log("compose", f"confidence={confidence} matches={len(state.matches)} "
                            f"aware={len(brief.things_to_be_aware_of)}")
        return {"brief": brief, "trace": state.trace}

    return compose


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
