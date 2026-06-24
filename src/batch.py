"""Batch runner (PRIMARY deliverable).

Reads all sample inquiries, runs each through the LangGraph agent, writes a
Markdown + JSON brief per lead, and a combined all_briefs.json.

    python -m src.batch                       # all leads -> output/briefs/
    python -m src.batch --inquiries path.json --out output/briefs
    python -m src.batch --lead LEAD-2026-003  # a single lead
"""
from __future__ import annotations

import argparse
import json
import os

from .agent import run_agent, runtime_info
from .config import get_settings
from .models import Inquiry


def load_inquiries(path: str) -> list[Inquiry]:
    with open(path, encoding="utf-8") as f:
        return [Inquiry(**row) for row in json.load(f)]


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description="Run the Buyer Lead Intake Agent over sample inquiries")
    ap.add_argument("--inquiries", default=s.inquiries_path)
    ap.add_argument("--out", default=s.output_dir)
    ap.add_argument("--lead", default=None, help="process only this lead_id")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    info = runtime_info()
    print(f"Runtime: LLM={info['llm_provider']} | data={info['matcher_backend']} "
          f"| listings={info['listings_loaded']}")
    print("-" * 72)

    inquiries = load_inquiries(args.inquiries)
    if args.lead:
        inquiries = [i for i in inquiries if i.lead_id == args.lead]
        if not inquiries:
            raise SystemExit(f"No inquiry with lead_id={args.lead}")

    combined = []
    for inq in inquiries:
        brief = run_agent(inq, persist=True, out_dir=args.out)
        combined.append(brief.model_dump())
        sec = " [SECURITY FLAG]" if brief.security_flag.triggered else ""
        print(f"{brief.lead_id}  {(brief.buyer_name or '')[:26]:<26}  "
              f"matches={len(brief.recommended_properties)}  "
              f"confidence={brief.confidence}{sec}")

    combined_path = os.path.join(args.out, "all_briefs.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, default=str)

    print("-" * 72)
    print(f"Wrote {len(combined)} briefs (.md + .json) to {args.out}")
    print(f"Combined: {combined_path}")


if __name__ == "__main__":
    main()
