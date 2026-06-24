"""Typed data models shared across the whole agent.

These are the contracts between nodes. Keeping them explicit (Pydantic) is part
of the agent design: each node reads/writes well-defined fields on the state,
so the LLM-vs-deterministic boundary stays legible.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Inbound inquiry (matches the website_form shape in sample_buyer_inquiries)
# --------------------------------------------------------------------------- #
class Inquiry(BaseModel):
    lead_id: str = "AD-HOC"
    received_at: Optional[str] = None
    channel: str = "website_form"
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_phone: Optional[str] = None
    message: str


class BuyerType(str, Enum):
    relocating = "relocating"
    family = "family"
    investor = "investor"
    first_timer = "first-timer"
    downsizer = "downsizer"
    unknown = "unknown"


# --------------------------------------------------------------------------- #
# Structured requirements extracted by the LLM (extract node)
# --------------------------------------------------------------------------- #
class BuyerProfile(BaseModel):
    locations: list[str] = Field(default_factory=list)
    budget: Optional[int] = None
    stretch_budget: Optional[int] = None
    min_beds: Optional[int] = None
    min_baths: Optional[float] = None
    property_type: Optional[str] = None  # Condo / Single Family / Townhouse / Villa / Multi-Family
    hard_must_haves: list[str] = Field(default_factory=list)
    soft_nice_to_haves: list[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    buyer_type: BuyerType = BuyerType.unknown
    is_cash_buyer: Optional[bool] = None
    special_needs: list[str] = Field(default_factory=list)
    emotional_context: Optional[str] = None

    # Engineering-judgment fields the extractor also fills:
    is_too_vague_to_match: bool = False
    requires_human_judgment: bool = False  # negotiation / seller motivation etc.
    human_judgment_reason: Optional[str] = None
    referenced_address: Optional[str] = None  # e.g. lead asking about a specific listing
    extraction_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Safety result (safety node) - deterministic, never trusts the LLM
# --------------------------------------------------------------------------- #
class SecurityFlag(BaseModel):
    triggered: bool = False
    category: Optional[str] = None  # e.g. "prompt_injection", "pii_exfiltration_attempt"
    detail: Optional[str] = None
    sanitized_message_preview: Optional[str] = None


# --------------------------------------------------------------------------- #
# A property match (match node) - note: owner_name / owner_phone are NEVER here
# --------------------------------------------------------------------------- #
class PropertyMatch(BaseModel):
    listing_id: str
    mls_number: str
    address: str
    neighborhood: str
    city: str
    price: int
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    property_type: str
    listing_status: str  # Active / Pending / Active Under Contract
    matched_features: list[str] = Field(default_factory=list)
    score: float = 0.0
    fits_in_budget: bool = True          # price <= budget
    fits_in_stretch_only: bool = False   # budget < price <= stretch_budget
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# The Lead Brief (compose node) - the deliverable
# --------------------------------------------------------------------------- #
class LeadBrief(BaseModel):
    lead_id: str
    buyer_name: Optional[str] = None
    generated_at: str
    buyer_summary: str
    recommended_properties: list[PropertyMatch] = Field(default_factory=list)
    things_to_be_aware_of: list[str] = Field(default_factory=list)
    suggested_next_action: str = ""
    confidence: str = "medium"  # high / medium / low
    confidence_notes: list[str] = Field(default_factory=list)
    security_flag: SecurityFlag = Field(default_factory=SecurityFlag)
    # carry the extracted profile for transparency / debugging
    buyer_profile: Optional[BuyerProfile] = None


# --------------------------------------------------------------------------- #
# LangGraph state - the single object that flows through the graph
# --------------------------------------------------------------------------- #
class AgentState(BaseModel):
    """The mutable state passed node-to-node. Each node fills its own slice."""
    inquiry: Inquiry
    profile: Optional[BuyerProfile] = None
    security_flag: SecurityFlag = Field(default_factory=SecurityFlag)
    matches: list[PropertyMatch] = Field(default_factory=list)
    brief: Optional[LeadBrief] = None

    # deterministic, data-driven concerns assembled by the match node
    data_concerns: list[str] = Field(default_factory=list)

    # persistence control: the batch runner sets these; the API leaves them off
    persist: bool = False
    out_dir: Optional[str] = None

    # bookkeeping for the writeup / debugging
    trace: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def log(self, node: str, msg: str) -> None:
        self.trace.append(f"[{node}] {msg}")
