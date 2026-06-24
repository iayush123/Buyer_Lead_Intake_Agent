"""Repository factory. Chooses Postgres or in-memory from settings, with a
graceful fallback to in-memory if Postgres can't be reached."""
from __future__ import annotations

from ..config import Settings
from .base import FilterCriteria, ListingRepository, ListingRow
from .scoring import score_and_rank, score_row


def get_repository(settings: Settings) -> ListingRepository:
    if settings.matcher_backend == "postgres":
        try:
            from .postgres_repo import PostgresRepository

            repo = PostgresRepository(settings.database_url, settings.price_outlier_threshold)
            repo.count()  # connectivity check
            return repo
        except Exception as exc:  # pragma: no cover - depends on env
            print(f"[data_layer] Postgres unavailable ({exc}); falling back to in-memory.")

    from .memory_repo import InMemoryRepository

    return InMemoryRepository(settings.mls_csv_path)


__all__ = [
    "get_repository",
    "ListingRepository",
    "ListingRow",
    "FilterCriteria",
    "score_and_rank",
    "score_row",
]
