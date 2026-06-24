"""Deterministic, offline 'LLM' provider.

This is NOT a real model. It is a rule/regex-based stand-in that implements the
exact same `extract()` / `compose()` contract as the real providers, so the
whole agent runs with zero API keys and produces reproducible briefs (useful for
CI, demos, and grading). When a real key is configured the factory swaps this
out for OpenAIProvider / AnthropicProvider with no other code change.

It parses budgets, beds, locations, hard-vs-soft wants (clause-scoped, so a cue
in one clause doesn't bleed into another), buyer type, cash, vagueness and
human-judgment triggers - using WORD-BOUNDARY matching so e.g. 'cat' does not
match inside 'relocating'.
"""
from __future__ import annotations

import re
from typing import Any

from ..vocab import (
    FEATURE_SYNONYMS,
    HUMAN_JUDGMENT_TRIGGERS,
    NEIGHBORHOOD_ALIASES,
    PROPERTY_TYPE_ALIASES,
    UNMATCHABLE_WANTS,
)
from .base import LLMProvider

HARD_CUES = (
    "non-negotiable", "must have", "must", "need", "needs", "needed", "required",
    "require", "essential", "have to", "at least", "can't do without",
    "cannot do without", "non negotiable",
)
SOFT_CUES = ("ideally", "prefer", "would like", "would love", "nice", "hope",
             "maybe", "open to", "like a", "want")

_MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s?([KkMm]?)")
_ADDRESS_RE = re.compile(
    r"\b(\d{2,6}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+"
    r"(?:Road|Rd|Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Terrace|Ter|"
    r"Lane|Ln|Court|Ct|Way|Place|Pl|Circle|Cir))\b"
)
_OPEN_LOCATION_RE = re.compile(r"open (on|to)\s+(any\s+)?(neighborhood|neighbourhood|location|area)")


def _wb(term: str, text: str) -> bool:
    """Whole-word(s) match, so 'cat' != 'relocating' and 'need' != 'needed'."""
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


def _money_to_int(num: str, suffix: str) -> int:
    val = float(num.replace(",", ""))
    if suffix.lower() == "k":
        val *= 1_000
    elif suffix.lower() == "m":
        val *= 1_000_000
    return int(round(val))


class MockProvider(LLMProvider):
    name = "mock"

    # ----------------------------- EXTRACT ----------------------------- #
    def extract(self, message: str) -> dict[str, Any]:
        text = message.strip()
        low = text.lower()
        notes: list[str] = []

        locations = self._locations(low)
        if _OPEN_LOCATION_RE.search(low) and locations:
            notes.append(f"Buyer says they're open on neighborhood (mentioned "
                         f"{', '.join(locations)} for commute) - not hard-filtering on location.")
            locations = []

        budget, stretch, money_notes = self._budget(text, low)
        notes += money_notes
        min_beds = self._min_beds(low)
        property_type, ptype_notes = self._property_type(low)
        notes += ptype_notes
        hard, soft = self._features(low)
        special_needs, limit_notes = self._special_needs(low)
        notes += limit_notes
        buyer_type = self._buyer_type(low)
        is_cash = self._is_cash(low)
        timeline = self._timeline(low)
        emotional = self._emotional(low, text)
        req_human, human_reason = self._human_judgment(low)
        ref_addr = self._referenced_address(text)

        too_vague = self._too_vague(min_beds, budget, locations, property_type, hard, soft, low)

        return {
            "locations": locations,
            "budget": budget,
            "stretch_budget": stretch,
            "min_beds": min_beds,
            "min_baths": None,
            "property_type": property_type,
            "hard_must_haves": hard,
            "soft_nice_to_haves": soft,
            "timeline": timeline,
            "buyer_type": buyer_type,
            "is_cash_buyer": is_cash,
            "special_needs": special_needs,
            "emotional_context": emotional,
            "is_too_vague_to_match": too_vague,
            "requires_human_judgment": req_human,
            "human_judgment_reason": human_reason,
            "referenced_address": ref_addr,
            "extraction_notes": notes,
        }

    def _locations(self, low: str) -> list[str]:
        found: list[str] = []
        for alias, canon in NEIGHBORHOOD_ALIASES.items():
            if _wb(alias, low) and canon not in found:
                found.append(canon)
        return found

    def _budget(self, text: str, low: str) -> tuple[int | None, int | None, list[str]]:
        notes: list[str] = []
        matches = list(_MONEY_RE.finditer(text))
        if not matches:
            return None, None, notes
        values = [(_money_to_int(m.group(1), m.group(2)), m.start()) for m in matches]

        stretch = None
        for val, pos in values:
            if "stretch" in low[max(0, pos - 30): pos]:
                stretch = val

        budget = None
        # range like "$500K-$900K" or "$500K to $900K"
        if len(values) >= 2 and stretch is None:
            v0, p0 = values[0]
            v1, p1 = values[1]
            between = text[p0:p1 + 10]
            if re.search(r"\$[\d.,]+\s?[KkMm]?\s?(?:-|to|–)\s?\$", between) and abs(p1 - p0) < 25:
                lo, hi = sorted([v0, v1])
                budget = hi
                notes.append(f"Budget stated as a range; using upper bound ${hi:,} (lower ~${lo:,}).")
                values = [v for v in values if v[0] not in (v0, v1)]

        if budget is None:
            ceiling = None
            for val, pos in values:
                window = low[max(0, pos - 25): pos]
                if any(c in window for c in ("up to", "under", "max", "budget", "around", "asking", "is ")):
                    ceiling = val
            budget = ceiling if ceiling is not None else (values[0][0] if values else None)

        if stretch and budget and stretch < budget:
            budget, stretch = stretch, budget
        return budget, stretch, notes

    def _min_beds(self, low: str) -> int | None:
        m = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:bedroom|bed|br)s?\b", low)
        if m:
            return int(m.group(1))
        m = re.search(r"(?:at least\s*)?(\d+)\s*\+?\s*(?:bedroom|bed|br)s?\b", low)
        if m:
            return int(m.group(1))
        return None

    def _property_type(self, low: str) -> tuple[str | None, list[str]]:
        hits: list[str] = []
        ordered = ["condominium", "starter condo", "condo", "townhouse", "townhome",
                   "town home", "multi-family", "multifamily", "duplex", "villa",
                   "single family", "single-family", "house", "home", "apartment"]
        for kw in ordered:
            if _wb(kw, low):
                canon = PROPERTY_TYPE_ALIASES[kw]
                if canon not in hits:
                    hits.append(canon)
        if not hits:
            return None, []
        if len(hits) == 1:
            return hits[0], []
        return None, [f"Buyer open to multiple property types ({', '.join(hits)}); not hard-filtering on type."]

    def _features(self, low: str) -> tuple[list[str], list[str]]:
        """Clause-scoped feature extraction. A hard cue only makes a feature hard
        if it occurs in the SAME clause as the feature mention."""
        clauses = re.split(r"[.;,]|\band\b|\bbut\b", low)
        hard: list[str] = []
        soft: list[str] = []
        assigned: set[str] = set()
        for clause in clauses:
            clause_is_hard = any(_wb(c, clause) for c in HARD_CUES)
            for phrase, tokens in FEATURE_SYNONYMS.items():
                if _wb(phrase, clause):
                    bucket = hard if clause_is_hard else soft
                    for tok in tokens:
                        if tok not in assigned:
                            assigned.add(tok)
                            bucket.append(tok)
        # if a token is in both (different clauses), prefer hard
        soft = [t for t in soft if t not in hard]
        return hard, soft

    def _special_needs(self, low: str) -> tuple[list[str], list[str]]:
        needs: list[str] = []
        notes: list[str] = []
        for phrase, explanation in UNMATCHABLE_WANTS.items():
            if _wb(phrase, low):
                if phrase not in needs:
                    needs.append(phrase)
                if explanation not in notes:
                    notes.append(explanation)
        deduped = [n for n in needs if not any(n != o and n in o for o in needs)]
        return deduped, notes

    def _buyer_type(self, low: str) -> str:
        if any(_wb(k, low) for k in ("investor", "investment", "rental", "cash-flowing",
                                     "cash flowing", "cap rate")) or "rent out" in low or "rented out" in low:
            return "investor"
        if "first-time" in low or "first time" in low:
            return "first-timer"
        if any(k in low for k in ("elderly parents", "my parents", "downsize", "downsizing")):
            return "downsizer"
        if any(_wb(k, low) for k in ("children", "kids")) or "family of" in low:
            return "family"
        if any(_wb(k, low) for k in ("relocating", "relocate")) or "new job" in low or "moving for" in low:
            return "relocating"
        return "unknown"

    def _is_cash(self, low: str) -> bool | None:
        if any(k in low for k in ("cash purchase", "all cash", "all-cash",
                                  "cash buyer", "pay cash", "in cash", "cash offer")):
            return True
        return None

    def _timeline(self, low: str) -> str | None:
        patterns = [
            (r"this week", "This week (urgent)"),
            (r"by (january|february|march|april|may|june|july|august|september|october|november|december)", None),
            (r"before year-?end", "Before year-end"),
            (r"(next|over the next)\s*\d+\s*months", None),
            (r"close before", "Closing before year-end"),
            (r"move-?in flexible|flexible", "Flexible"),
        ]
        for pat, label in patterns:
            mt = re.search(pat, low)
            if mt:
                return label if label else mt.group(0).title()
        return None

    def _emotional(self, low: str, text: str) -> str | None:
        cues = []
        if "nervous" in low:
            cues.append("expresses nervousness about the process (reassurance will help)")
        if any(k in low for k in ("brutal", "winters", "love it", "loves it")):
            cues.append("relocation driven by lifestyle; warm/relationship-oriented tone")
        if len(text) > 500:
            cues.append("long, chatty message with lots of personal/family context (in research mode)")
        if any(k in low for k in ("excited", "can't wait", "dream")):
            cues.append("emotionally invested / excited")
        if not cues:
            return None
        return "; ".join(cues[:2]).capitalize()

    def _human_judgment(self, low: str) -> tuple[bool, str | None]:
        reasons = []
        for k, v in HUMAN_JUDGMENT_TRIGGERS.items():
            if (_wb(k, low) if " " not in k else k in low):
                reasons.append(v)
        if reasons:
            return True, " ".join(dict.fromkeys(reasons))
        return False, None

    def _referenced_address(self, text: str) -> str | None:
        m = _ADDRESS_RE.search(text)
        return m.group(1) if m else None

    def _too_vague(self, min_beds, budget, locations, ptype, hard, soft, low) -> bool:
        generic = any(k in low for k in (
            "good investment property", "what options", "what you have",
            "not sure what", "just looking", "see what's out there",
        ))
        no_criteria = (min_beds is None and budget is None and not locations
                       and ptype is None and not hard and not soft)
        return bool(generic or no_criteria)

    # ----------------------------- COMPOSE ----------------------------- #
    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = payload["profile"]
        matches = payload["matches"]
        buyer = payload.get("buyer_name") or "the buyer"

        reasons = {m["listing_id"]: self._reason(m) for m in matches}
        return {
            "buyer_summary": self._summary(profile, buyer),
            "property_reasons": reasons,
            "things_to_be_aware_of": [],   # node merges deterministic concerns
            "suggested_next_action": "",   # node sets this deterministically
        }

    @staticmethod
    def _art(word: str) -> str:
        return "an" if word[:1].lower() in "aeiou" else "a"

    def _summary(self, p: dict[str, Any], buyer: str) -> str:
        parts = []
        bt = p.get("buyer_type")
        bt = getattr(bt, "value", bt)  # normalize enum member → plain string ("family", not "BuyerType.family")
        bt_label = "" if bt in (None, "unknown") else f"{bt} buyer"
        beds = f"{p['min_beds']}+ bed " if p.get("min_beds") else ""
        ptype = (p.get("property_type") or "home").lower()
        locs = ", ".join(p.get("locations") or []) or "the Miami area (location open)"
        budget = p.get("budget")
        budget_s = f" around ${budget:,}" if budget else " (budget not stated)"
        lead = f"{buyer} is {self._art(bt)} {bt_label} " if bt_label else f"{buyer} is "
        what = f"{beds}{ptype}"
        parts.append(f"{lead}looking for {self._art(what)} {what} in {locs}{budget_s}.".replace("  ", " "))

        if p.get("hard_must_haves"):
            parts.append(f"Hard must-haves: {', '.join(p['hard_must_haves'])}.")
        if p.get("soft_nice_to_haves"):
            parts.append(f"Nice-to-haves: {', '.join(p['soft_nice_to_haves'])}.")
        if p.get("timeline"):
            parts.append(f"Timeline: {p['timeline']}.")
        if p.get("is_cash_buyer"):
            parts.append("Cash purchase.")
        if p.get("emotional_context"):
            parts.append(f"Context: {p['emotional_context']}.")
        return " ".join(parts)

    def _reason(self, m: dict[str, Any]) -> str:
        bits = []
        beds = m.get("bedrooms")
        bed_s = f"{beds}BR" if beds not in (None, 0) else "studio"
        bits.append(f"{m['address']} ({m['neighborhood']}) - ${m['price']:,}, {bed_s} {m['property_type']}.")
        if m.get("matched_features"):
            bits.append(f"Hits: {', '.join(m['matched_features'])}.")
        if m.get("fits_in_stretch_only"):
            bits.append("Above the base budget - only fits the stretch budget.")
        status = m.get("listing_status")
        if status and status != "Active":
            bits.append(f"Status is '{status}', not freely available.")
        return " ".join(bits)
