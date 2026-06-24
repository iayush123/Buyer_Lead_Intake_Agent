"""Shared CSV parsing + cleaning. Used by BOTH the in-memory repo and the
Postgres loader, so the messy-data handling (studios, blanks, the $250M outlier,
semicolon features) is defined in exactly one place.
"""
from __future__ import annotations

import csv
from typing import Optional

from ..config import get_settings
from .base import ListingRow

PRICE_OUTLIER_THRESHOLD = get_settings().price_outlier_threshold


def _to_int(v: str) -> Optional[int]:
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _to_float(v: str) -> Optional[float]:
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_features(raw: str) -> list[str]:
    return [f.strip() for f in (raw or "").split(";") if f.strip()]


def parse_row(r: dict) -> ListingRow:
    price = _to_int(r.get("price", "")) or 0
    beds = _to_int(r.get("bedrooms", ""))
    # studios appear as 0 or blank beds -> normalize blank to 0 so they're
    # treated as studios (0 beds), not "unknown".
    if beds is None:
        beds = 0
    return ListingRow(
        listing_id=r["listing_id"].strip(),
        mls_number=r.get("mls_number", "").strip(),
        address=r.get("address", "").strip(),
        neighborhood=r.get("neighborhood", "").strip(),
        city=r.get("city", "").strip(),
        zip_code=r.get("zip_code", "").strip(),
        price=price,
        bedrooms=beds,
        bathrooms=_to_float(r.get("bathrooms", "")),
        sqft=_to_int(r.get("sqft", "")),
        year_built=_to_int(r.get("year_built", "")),
        property_type=r.get("property_type", "").strip(),
        listing_status=r.get("listing_status", "").strip(),
        days_on_market=_to_int(r.get("days_on_market", "")),
        description=r.get("description", "").strip(),
        features=parse_features(r.get("features", "")),
        is_price_outlier=price > PRICE_OUTLIER_THRESHOLD,
    )


def load_rows(csv_path: str) -> list[ListingRow]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [parse_row(r) for r in csv.DictReader(f)]
