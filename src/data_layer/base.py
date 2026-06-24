"""Data-layer interface + the row type the rest of the app is allowed to see.

PII enforcement happens HERE, structurally: `ListingRow` has no owner_name /
owner_phone fields, and the repositories never select them. Even if a downstream
node (or the LLM) is told to leak them, the data simply isn't in memory to leak.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..config import Settings
from ..models import BuyerProfile


@dataclass
class ListingRow:
    listing_id: str
    mls_number: str
    address: str
    neighborhood: str
    city: str
    zip_code: str
    price: int
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    sqft: Optional[int]
    year_built: Optional[int]
    property_type: str
    listing_status: str
    days_on_market: Optional[int]
    description: str
    features: list[str] = field(default_factory=list)
    is_price_outlier: bool = False
    # NOTE: owner_name / owner_phone are intentionally absent.


@dataclass
class FilterCriteria:
    """The hard constraints, already normalized from the BuyerProfile.
    Both the SQL repo and the in-memory repo consume this identical object."""
    neighborhoods: list[str]
    price_ceiling: Optional[int]            # stretch budget if present, else budget
    min_beds: Optional[int]
    property_type: Optional[str]
    required_features: list[str]            # hard must-haves that are real MLS tokens
    exclude_outliers: bool = True

    @classmethod
    def from_profile(cls, profile: BuyerProfile, settings: Settings,
                     known_features: list[str]) -> "FilterCriteria":
        ceiling = profile.stretch_budget or profile.budget
        required = [f for f in profile.hard_must_haves if f in known_features]
        return cls(
            neighborhoods=list(profile.locations),
            price_ceiling=ceiling,
            min_beds=profile.min_beds,
            property_type=profile.property_type,
            required_features=required,
        )


class ListingRepository(ABC):
    """Deterministic data access. No LLM, ever."""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def hard_filter(self, criteria: FilterCriteria) -> list[ListingRow]:
        """Return listings satisfying ALL hard constraints (owner PII excluded)."""

    @abstractmethod
    def get_by_address(self, address_fragment: str) -> Optional[ListingRow]:
        """Look up a specific listing a buyer referenced by address."""
