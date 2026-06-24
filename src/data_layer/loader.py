"""Load the MLS CSV into Postgres.

Usage:
    python -m src.data_layer.loader            # uses DATABASE_URL + MLS_CSV_PATH
    python -m src.data_layer.loader --csv path/to.csv

Idempotent: it creates the schema if missing and upserts on listing_id. This is
the one place owner_name / owner_phone are written; the app never reads them.
"""
from __future__ import annotations

import argparse
import csv
import os

from ..config import get_settings


def _int(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


def _float(v):
    v = (v or "").strip()
    return float(v) if v else None


def run(csv_path: str, database_url: str, schema_path: str) -> int:
    import psycopg

    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            beds = _int(r.get("bedrooms"))
            rows.append((
                r["listing_id"].strip(), r.get("mls_number", "").strip(),
                r.get("address", "").strip(), r.get("neighborhood", "").strip(),
                r.get("city", "").strip(), r.get("state", "").strip(),
                r.get("zip_code", "").strip(), _int(r.get("price")) or 0,
                beds, _float(r.get("bathrooms")), _int(r.get("sqft")),
                _int(r.get("year_built")), r.get("property_type", "").strip(),
                r.get("listing_status", "").strip(),
                r.get("date_listed") or None, r.get("last_updated") or None,
                _int(r.get("days_on_market")), r.get("description", "").strip(),
                r.get("features", "").strip(), r.get("owner_name", "").strip(),
                r.get("owner_phone", "").strip(),
            ))

    insert = """
        INSERT INTO listings (
            listing_id, mls_number, address, neighborhood, city, state, zip_code,
            price, bedrooms, bathrooms, sqft, year_built, property_type,
            listing_status, date_listed, last_updated, days_on_market,
            description, features, owner_name, owner_phone
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (listing_id) DO UPDATE SET
            price = EXCLUDED.price,
            listing_status = EXCLUDED.listing_status,
            last_updated = EXCLUDED.last_updated,
            days_on_market = EXCLUDED.days_on_market;
    """

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(schema_sql)
        cur.executemany(insert, rows)
        conn.commit()
    return len(rows)


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description="Load MLS CSV into Postgres")
    ap.add_argument("--csv", default=s.mls_csv_path)
    ap.add_argument("--database-url", default=s.database_url)
    args = ap.parse_args()
    schema_path = os.path.join(s.project_root, "sql", "schema.sql")
    n = run(args.csv, args.database_url, schema_path)
    print(f"Loaded/updated {n} listings into {args.database_url}")


if __name__ == "__main__":
    main()
