"""Central configuration. Reads from environment with safe, offline-friendly
defaults so the agent runs with zero setup."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _root() -> str:
    # project root = parent of src/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


try:
    from dotenv import load_dotenv

    # Load ONLY this project's .env (do not walk up into unrelated projects).
    load_dotenv(os.path.join(_root(), ".env"))
except Exception:  # python-dotenv is optional
    pass


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    # Data layer
    matcher_backend: str = os.getenv("MATCHER_BACKEND", "memory").lower()
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://agentmira:agentmira@localhost:5432/agentmira",
    )
    mls_csv_path: str = os.getenv("MLS_CSV_PATH", os.path.join(_root(), "data", "miami_mls_listings.csv"))

    # Paths
    project_root: str = _root()
    inquiries_path: str = os.path.join(_root(), "data", "sample_buyer_inquiries.json")
    output_dir: str = os.path.join(_root(), "output", "briefs")

    # Matching knobs
    max_matches: int = 5
    min_matches_to_show: int = 1

    # Business rules
    price_outlier_threshold: int = 50_000_000  # listings above this are treated as data errors


def get_settings() -> Settings:
    return Settings()
