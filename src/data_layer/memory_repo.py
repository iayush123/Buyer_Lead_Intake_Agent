"""In-memory repository - the zero-setup fallback for the Postgres repo.

It implements the SAME hard-filter semantics as postgres_repo.py's SQL, in pure
Python, so the agent behaves identically whether or not a database is running.
Tradeoff vs Postgres is documented in the README / writeup.
"""
from __future__ import annotations

from typing import Optional

from .base import FilterCriteria, ListingRepository, ListingRow
from .csv_util import load_rows


class InMemoryRepository(ListingRepository):
    def __init__(self, csv_path: str) -> None:
        self._rows: list[ListingRow] = load_rows(csv_path)

    def count(self) -> int:
        return len(self._rows)

    def hard_filter(self, c: FilterCriteria) -> list[ListingRow]:
        out: list[ListingRow] = []
        nbhds = {n.lower() for n in c.neighborhoods}
        req_feats = {f.lower() for f in c.required_features}
        for row in self._rows:
            if c.exclude_outliers and row.is_price_outlier:
                continue
            if nbhds and row.neighborhood.lower() not in nbhds:
                continue
            if c.price_ceiling is not None and row.price > c.price_ceiling:
                continue
            if c.min_beds is not None and (row.bedrooms or 0) < c.min_beds:
                continue
            if c.property_type and row.property_type.lower() != c.property_type.lower():
                continue
            if req_feats:
                have = {f.lower() for f in row.features}
                if not req_feats.issubset(have):
                    continue
            out.append(row)
        return out

    def get_by_address(self, address_fragment: str) -> Optional[ListingRow]:
        frag = address_fragment.lower().strip()
        for row in self._rows:
            if frag and frag in row.address.lower():
                return row
        return None
