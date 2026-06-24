"""Soft-preference scoring & ranking - pure, deterministic, testable.

Runs AFTER the repository's hard filter. Survivors are scored on nice-to-haves,
availability and budget comfort, then ranked. No LLM involvement. The per-match
`reasons` / `caveats` produced here are what the realtor ultimately reads.
"""
from __future__ import annotations

from ..models import BuyerProfile, PropertyMatch
from .base import ListingRow

STATUS_WEIGHT = {"Active": 1.5, "Active Under Contract": 0.5, "Pending": 0.0}
SOFT_FEATURE_POINTS = 2.0
HARD_FEATURE_POINTS = 1.0
IN_BUDGET_POINTS = 1.0
EXTRA_BED_POINTS = 0.5


def _bed_label(beds: int | None) -> str:
    return "studio" if beds in (None, 0) else f"{beds}BR"


def score_row(profile: BuyerProfile, row: ListingRow) -> PropertyMatch:
    soft_wanted = {f.lower(): f for f in profile.soft_nice_to_haves}
    hard_wanted = {f.lower(): f for f in profile.hard_must_haves}
    have = {f.lower(): f for f in row.features}

    matched_soft = [orig for k, orig in soft_wanted.items() if k in have]
    matched_hard = [orig for k, orig in hard_wanted.items() if k in have]

    budget = profile.budget
    stretch = profile.stretch_budget
    fits_in_budget = budget is None or row.price <= budget
    fits_in_stretch_only = bool(
        budget is not None and row.price > budget and stretch and row.price <= stretch
    )

    score = 0.0
    score += SOFT_FEATURE_POINTS * len(matched_soft)
    score += HARD_FEATURE_POINTS * len(matched_hard)
    score += STATUS_WEIGHT.get(row.listing_status, 0.0)
    if fits_in_budget:
        score += IN_BUDGET_POINTS
    if profile.min_beds is not None and (row.bedrooms or 0) > profile.min_beds:
        score += EXTRA_BED_POINTS

    reasons: list[str] = []
    if profile.locations:
        reasons.append(f"In {row.neighborhood}, a requested area")
    if budget is not None:
        if fits_in_stretch_only:
            reasons.append(f"${row.price:,} - within the stretch budget (above the ${budget:,} base)")
        elif fits_in_budget:
            reasons.append(f"${row.price:,} - within budget")
    if profile.min_beds is not None:
        reasons.append(f"{_bed_label(row.bedrooms)} meets the {profile.min_beds}+ bedroom need")
    if matched_hard:
        reasons.append(f"Has must-have {', '.join(matched_hard)}")
    if matched_soft:
        reasons.append(f"Also offers {', '.join(matched_soft)}")

    caveats: list[str] = []
    if row.listing_status != "Active":
        caveats.append(
            f"Status is '{row.listing_status}' - not freely available; confirm it's still in play before showing."
        )
    if fits_in_stretch_only:
        caveats.append("Priced above the base budget; only works if the stretch budget is real.")
    missing_soft = [orig for k, orig in soft_wanted.items() if k not in have]
    if matched_soft and missing_soft:
        caveats.append(f"Does not list: {', '.join(missing_soft)}.")

    return PropertyMatch(
        listing_id=row.listing_id,
        mls_number=row.mls_number,
        address=row.address,
        neighborhood=row.neighborhood,
        city=row.city,
        price=row.price,
        bedrooms=row.bedrooms,
        bathrooms=row.bathrooms,
        sqft=row.sqft,
        property_type=row.property_type,
        listing_status=row.listing_status,
        matched_features=matched_hard + matched_soft,
        score=round(score, 2),
        fits_in_budget=fits_in_budget,
        fits_in_stretch_only=fits_in_stretch_only,
        reasons=reasons,
        caveats=caveats,
    )


def score_and_rank(profile: BuyerProfile, rows: list[ListingRow], top_n: int) -> list[PropertyMatch]:
    scored = [score_row(profile, r) for r in rows]
    scored.sort(
        key=lambda m: (m.score, m.fits_in_budget, -m.price),
        reverse=True,
    )
    return scored[:top_n]
