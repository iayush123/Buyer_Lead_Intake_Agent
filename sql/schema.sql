-- MLS listings table. Mirrors the CSV, but models the messy bits explicitly:
--   * bedrooms is nullable / can be 0 (studios)
--   * bathrooms is nullable (blank in source)
--   * a generated flag marks the $250M+ data-error outlier
-- owner_name / owner_phone are stored (this is the system of record) but the
-- application layer NEVER selects them — PII stays in the database.

CREATE TABLE IF NOT EXISTS listings (
    listing_id      TEXT PRIMARY KEY,
    mls_number      TEXT,
    address         TEXT NOT NULL,
    neighborhood    TEXT,
    city            TEXT,
    state           TEXT,
    zip_code        TEXT,
    price           BIGINT NOT NULL,
    bedrooms        INTEGER,          -- nullable; 0 = studio
    bathrooms       NUMERIC(4,1),     -- nullable
    sqft            INTEGER,
    year_built      INTEGER,
    property_type   TEXT,
    listing_status  TEXT,             -- Active / Pending / Active Under Contract
    date_listed     DATE,
    last_updated    DATE,
    days_on_market  INTEGER,
    description     TEXT,
    features        TEXT,             -- semicolon-separated; parsed in app
    owner_name      TEXT,             -- PII: never SELECTed by the app
    owner_phone     TEXT,             -- PII: never SELECTed by the app
    is_price_outlier BOOLEAN GENERATED ALWAYS AS (price > 50000000) STORED
);

-- Indexes supporting the hard-filter predicates.
CREATE INDEX IF NOT EXISTS idx_listings_neighborhood ON listings (lower(neighborhood));
CREATE INDEX IF NOT EXISTS idx_listings_price        ON listings (price);
CREATE INDEX IF NOT EXISTS idx_listings_beds         ON listings (bedrooms);
CREATE INDEX IF NOT EXISTS idx_listings_type         ON listings (lower(property_type));
CREATE INDEX IF NOT EXISTS idx_listings_status       ON listings (listing_status);
