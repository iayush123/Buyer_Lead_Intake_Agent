"""Node 4 - Match against the MLS (DETERMINISTIC DATA WORK).

No LLM here. We:
  1. Refuse to match leads that are too vague (recommend a qualifying call).
  2. Handle leads that reference a specific listing (pull factual context only).
  3. Otherwise: hard-filter via the repository (SQL or in-memory) on
     location / price / beds / type / must-have features, then score & rank
     survivors on soft preferences + availability.
We also assemble the deterministic 'things to be aware of' (data_concerns):
budget-below-market, stretch-only, non-Active status mix, unverifiable wants,
and the $250M outlier exclusion.
"""
from __future__ import annotations

from ..data_layer.base import FilterCriteria
from ..data_layer.scoring import score_and_rank
from ..models import AgentState, BuyerProfile
from ..vocab import KNOWN_FEATURES
from .deps import Deps


def _budget_gap_note(deps: Deps, profile: BuyerProfile) -> str | None:
    """If nothing matched, was price the binding constraint? Report the gap."""
    if profile.budget is None:
        return None
    no_price = FilterCriteria.from_profile(profile, deps.settings, KNOWN_FEATURES)
    no_price.price_ceiling = None
    rows = deps.repo.hard_filter(no_price)
    if not rows:
        return None
    cheapest = min(r.price for r in rows)
    ceiling = profile.stretch_budget or profile.budget
    if cheapest > ceiling:
        crit = []
        if profile.locations:
            crit.append(", ".join(profile.locations))
        if profile.min_beds:
            crit.append(f"{profile.min_beds}+ beds")
        if profile.property_type:
            crit.append(profile.property_type)
        crit_s = " / ".join(crit) if crit else "these criteria"
        return (f"Budget appears below market: lowest listing for {crit_s} is "
                f"${cheapest:,}, above the stated budget of ${ceiling:,}. "
                f"The buyer likely needs to adjust expectations or budget.")
    return None


def make_match_node(deps: Deps):
    def match(state: AgentState) -> dict:
        profile = state.profile
        concerns: list[str] = []
        matches = []

        # carry forward extraction-level limitations (unmatchable wants)
        for note in (profile.extraction_notes or []):
            concerns.append(note)

        # --- (1) referenced-listing leads (e.g. negotiation questions) --------
        if profile.referenced_address:
            row = deps.repo.get_by_address(profile.referenced_address)
            if row:
                from ..data_layer.scoring import score_row
                m = score_row(profile, row)
                m.reasons = [f"This is the specific listing the buyer asked about "
                             f"({row.address}, {row.neighborhood}). Listed at ${row.price:,}, "
                             f"status '{row.listing_status}'."]
                m.caveats.append("Provided for factual context only - pricing/offer strategy "
                                 "is a realtor decision (see escalation below).")
                matches = [m]
                concerns.append(f"Buyer referenced a specific listing ({row.address}); included "
                                f"for context. Asking ${row.price:,}.")
            else:
                concerns.append(f"Buyer referenced an address ('{profile.referenced_address}') "
                                f"not found in the current MLS dataset; confirm the listing.")
            if profile.requires_human_judgment and profile.human_judgment_reason:
                concerns.append("ESCALATE TO REALTOR: " + profile.human_judgment_reason)
            state.matches = matches
            state.data_concerns = _dedupe(concerns)
            state.log("match", f"referenced-listing path, matches={len(matches)}")
            return {"matches": matches, "data_concerns": state.data_concerns, "trace": state.trace}

        # --- (2) too-vague leads: do NOT fabricate matches --------------------
        if profile.is_too_vague_to_match:
            concerns.append("Inquiry is too vague to match responsibly (missing budget, "
                            "location, size, or property type). Recommending a qualifying "
                            "call instead of guessing.")
            if profile.requires_human_judgment and profile.human_judgment_reason:
                concerns.append("ESCALATE TO REALTOR: " + profile.human_judgment_reason)
            state.matches = []
            state.data_concerns = _dedupe(concerns)
            state.log("match", "too-vague, no matches fabricated")
            return {"matches": [], "data_concerns": state.data_concerns, "trace": state.trace}

        # --- (3) normal hard-filter + score path ------------------------------
        criteria = FilterCriteria.from_profile(profile, deps.settings, KNOWN_FEATURES)
        rows = deps.repo.hard_filter(criteria)
        matches = score_and_rank(profile, rows, deps.settings.max_matches)
        state.matches = matches

        if not matches:
            gap = _budget_gap_note(deps, profile)
            if gap:
                concerns.append(gap)
            else:
                concerns.append("No current listings satisfy all hard constraints "
                                "(location / price / beds / type / must-haves). Suggest "
                                "broadening criteria or setting up a saved search.")
        else:
            # budget tier mix
            if all(m.fits_in_stretch_only for m in matches):
                concerns.append("Every recommended home sits above the base budget and only "
                                "fits the stretch budget - confirm the stretch number is real.")
            # availability mix
            non_active = [m for m in matches if m.listing_status != "Active"]
            if non_active:
                concerns.append(f"{len(non_active)} of {len(matches)} recommendations are "
                                f"'Pending' / 'Active Under Contract' - flagged per-property; "
                                f"they may fall through but aren't freely available.")
            # required features that were unmatchable (asked-for but not real MLS fields)
            unmatchable_hard = [h for h in profile.hard_must_haves if h not in KNOWN_FEATURES]
            if unmatchable_hard:
                concerns.append("Some must-haves can't be verified from MLS data "
                                f"({', '.join(unmatchable_hard)}); confirm with listing agents.")

        if profile.requires_human_judgment and profile.human_judgment_reason:
            concerns.append("ESCALATE TO REALTOR: " + profile.human_judgment_reason)

        state.data_concerns = _dedupe(concerns)
        state.log("match", f"candidates={len(rows)} ranked={len(matches)} "
                          f"concerns={len(state.data_concerns)}")
        return {"matches": matches, "data_concerns": state.data_concerns, "trace": state.trace}

    return match


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
