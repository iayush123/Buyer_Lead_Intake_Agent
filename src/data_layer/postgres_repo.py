"""PostgreSQL repository - the 'real' data layer.

Hard-constraint matching is expressed as a parameterized SQL query, which is the
point of using Postgres here: it shows real data modeling and makes the matching
push-down explicit. Crucially, the SELECT never lists owner_name / owner_phone,
so PII never leaves the database.

Requires a running Postgres (see docker-compose.yml) loaded via loader.py. If you
don't want to run a DB, set MATCHER_BACKEND=memory and the agent uses the
identical in-memory logic instead.
"""
from __future__ import annotations

from typing import Optional

from .base import FilterCriteria, ListingRepository, ListingRow

# Columns we are willing to read. owner_name / owner_phone deliberately omitted.
_SELECT_COLS = (
    "listing_id, mls_number, address, neighborhood, city, zip_code, price, "
    "bedrooms, bathrooms, sqft, year_built, property_type, listing_status, "
    "days_on_market, description, features"
)


class PostgresRepository(ListingRepository):
    def __init__(self, database_url: str, outlier_threshold: int) -> None:
        import psycopg  # lazy import; only needed for this backend

        self._psycopg = psycopg
        self._url = database_url
        self._outlier_threshold = outlier_threshold

    def _conn(self):
        return self._psycopg.connect(self._url, row_factory=self._psycopg.rows.dict_row)

    def _to_row(self, r: dict) -> ListingRow:
        feats = r.get("features") or ""
        feat_list = [f.strip() for f in feats.split(";") if f.strip()]
        return ListingRow(
            listing_id=r["listing_id"], mls_number=r["mls_number"], address=r["address"],
            neighborhood=r["neighborhood"], city=r["city"], zip_code=r["zip_code"],
            price=r["price"], bedrooms=r["bedrooms"], bathrooms=r["bathrooms"],
            sqft=r["sqft"], year_built=r["year_built"], property_type=r["property_type"],
            listing_status=r["listing_status"], days_on_market=r["days_on_market"],
            description=r["description"] or "", features=feat_list,
            is_price_outlier=(r["price"] or 0) > self._outlier_threshold,
        )

    def count(self) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM listings")
            return cur.fetchone()["n"]

    def hard_filter(self, c: FilterCriteria) -> list[ListingRow]:
        where = []
        params: dict = {}

        if c.exclude_outliers:
            where.append("price <= %(outlier)s")
            params["outlier"] = self._outlier_threshold
        if c.neighborhoods:
            where.append("lower(neighborhood) = ANY(%(nbhds)s)")
            params["nbhds"] = [n.lower() for n in c.neighborhoods]
        if c.price_ceiling is not None:
            where.append("price <= %(ceiling)s")
            params["ceiling"] = c.price_ceiling
        if c.min_beds is not None:
            where.append("COALESCE(bedrooms, 0) >= %(min_beds)s")
            params["min_beds"] = c.min_beds
        if c.property_type:
            where.append("lower(property_type) = %(ptype)s")
            params["ptype"] = c.property_type.lower()
        # require each hard must-have feature to be present in the features text
        for i, feat in enumerate(c.required_features):
            key = f"feat{i}"
            where.append(f"lower(features) LIKE %({key})s")
            params[key] = f"%{feat.lower()}%"

        sql = f"SELECT {_SELECT_COLS} FROM listings"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY price ASC"

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [self._to_row(r) for r in cur.fetchall()]

    def get_by_address(self, address_fragment: str) -> Optional[ListingRow]:
        sql = f"SELECT {_SELECT_COLS} FROM listings WHERE lower(address) LIKE %(frag)s LIMIT 1"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, {"frag": f"%{address_fragment.lower()}%"})
            r = cur.fetchone()
            return self._to_row(r) if r else None
