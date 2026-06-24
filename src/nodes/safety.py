"""Node 3 - Safety / instruction-boundary check (DETERMINISTIC).

The inquiry is treated strictly as data. This node scans for embedded
instructions / PII-exfiltration attempts and records a security flag. It does NOT
ask the LLM whether the text is safe - that would re-introduce the very trust
boundary we're trying to protect. The structural guarantee that owner_name /
owner_phone are never loaded by the data layer is the real backstop; this node
makes the attempt visible to the realtor.
"""
from __future__ import annotations

import re

from ..models import AgentState, SecurityFlag
from .deps import Deps

# (regex, category, human description)
INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (r"ignore\s+(all\s+)?previous\s+instructions", "prompt_injection",
     "Message tries to override the agent's instructions."),
    (r"disregard\s+(all\s+)?(previous|prior)", "prompt_injection",
     "Message tries to override the agent's instructions."),
    (r"owner('?s)?\s+(name|phone|contact|number)", "pii_exfiltration_attempt",
     "Message asks for owner names / phone numbers (PII)."),
    (r"(dump|list|export|reveal|send)\s+(all\s+)?(owner|seller|contact)", "pii_exfiltration_attempt",
     "Message asks to dump owner/seller contact data."),
    (r"phone numbers? from the database", "pii_exfiltration_attempt",
     "Message asks for phone numbers from the database (PII)."),
    (r"system\s+prompt|reveal your (instructions|prompt)", "prompt_injection",
     "Message tries to extract the system prompt."),
    (r"in json format so i can contact", "pii_exfiltration_attempt",
     "Message tries to harvest contact details."),
]


def make_safety_node(deps: Deps):
    def safety(state: AgentState) -> dict:
        text = (state.inquiry.message or "").lower()
        hits = [(cat, desc, pat) for pat, cat, desc in INJECTION_PATTERNS if re.search(pat, text)]

        if not hits:
            state.log("safety", "clean")
            return {"security_flag": SecurityFlag(triggered=False), "trace": state.trace}

        # categorize: PII attempts are the more serious bucket
        categories = {c for c, _, _ in hits}
        category = "pii_exfiltration_attempt" if "pii_exfiltration_attempt" in categories else "prompt_injection"
        detail = (
            "Embedded instruction(s) detected and NOT executed: "
            + "; ".join(sorted({d for _, d, _ in hits}))
            + " The agent processed only the genuine home-search request. "
              "Owner PII is never accessible to the agent."
        )
        # best-effort sanitized preview: drop sentences containing a trigger
        sentences = re.split(r"(?<=[.!?])\s+", state.inquiry.message)
        kept = [s for s in sentences if not any(re.search(p, s.lower()) for p, _, _ in INJECTION_PATTERNS)]
        preview = " ".join(kept).strip()

        flag = SecurityFlag(
            triggered=True, category=category, detail=detail,
            sanitized_message_preview=preview or None,
        )
        state.log("safety", f"FLAGGED category={category} hits={len(hits)}")
        return {"security_flag": flag, "trace": state.trace}

    return safety
