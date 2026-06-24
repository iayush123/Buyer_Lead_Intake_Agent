"""Render a LeadBrief to phone-readable Markdown. Pure formatting, no logic.
Used by the persist node (files) and the API (preview)."""
from __future__ import annotations

from .models import LeadBrief

_STATUS_BADGE = {
    "Active": "🟢 Active",
    "Active Under Contract": "🟡 Active Under Contract",
    "Pending": "🔴 Pending",
}


def brief_to_markdown(brief: LeadBrief) -> str:
    L: list[str] = []
    name = brief.buyer_name or "Unknown buyer"
    L.append(f"# Lead Brief - {name}")
    L.append(f"_Lead {brief.lead_id} · generated {brief.generated_at} · "
             f"confidence: **{brief.confidence.upper()}**_")
    L.append("")

    if brief.security_flag.triggered:
        L.append(f"> ⚠️ **SECURITY NOTICE** - {brief.security_flag.detail}")
        L.append("")

    L.append("## Buyer summary")
    L.append(brief.buyer_summary or "_(none)_")
    L.append("")

    L.append("## Recommended properties")
    if not brief.recommended_properties:
        L.append("_No properties recommended - see 'Things to be aware of' below._")
    else:
        for i, m in enumerate(brief.recommended_properties, 1):
            beds = "studio" if m.bedrooms in (None, 0) else f"{m.bedrooms}BR"
            baths = f"/{m.bathrooms}ba" if m.bathrooms else ""
            badge = _STATUS_BADGE.get(m.listing_status, m.listing_status)
            L.append(f"### {i}. {m.address}, {m.neighborhood} - ${m.price:,}")
            L.append(f"{beds}{baths} · {m.property_type} · {badge} · MLS {m.mls_number}")
            for r in m.reasons:
                L.append(f"- {r}")
            for c in m.caveats:
                L.append(f"  - ⚠️ {c}")
            L.append("")

    L.append("## Things to be aware of")
    if brief.things_to_be_aware_of:
        for c in brief.things_to_be_aware_of:
            L.append(f"- {c}")
    else:
        L.append("- Nothing notable.")
    L.append("")

    L.append("## Suggested next action")
    L.append(brief.suggested_next_action or "_(none)_")
    L.append("")

    if brief.confidence_notes:
        L.append("## Confidence notes")
        for n in brief.confidence_notes:
            L.append(f"- {n}")
        L.append("")

    return "\n".join(L).rstrip() + "\n"
