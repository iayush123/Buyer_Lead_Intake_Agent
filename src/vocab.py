"""Domain vocabulary - the single source of truth for how free-text buyer
language maps onto the *actual* MLS schema.

This module is deliberately data-only (no logic). Both the extractor (language
side) and the matcher (data side) import from here so the two stay in sync.
Everything here was derived by inspecting the real CSV's distinct values.
"""
from __future__ import annotations

# Distinct neighborhoods present in miami_mls_listings.csv
NEIGHBORHOODS: list[str] = [
    "Aventura", "Bal Harbour", "Brickell", "Coconut Grove", "Coral Gables",
    "Doral", "Downtown Miami", "Edgewater", "Key Biscayne", "Miami Beach",
    "Mid-Beach", "North Beach", "North Miami", "Pinecrest", "South Beach",
    "Wynwood",
]

# Common ways buyers refer to a neighborhood -> canonical MLS neighborhood
NEIGHBORHOOD_ALIASES: dict[str, str] = {
    "downtown": "Downtown Miami",
    "downtown miami": "Downtown Miami",
    "brickell": "Brickell",
    "coral gables": "Coral Gables",
    "the gables": "Coral Gables",
    "coconut grove": "Coconut Grove",
    "the grove": "Coconut Grove",
    "pinecrest": "Pinecrest",
    "aventura": "Aventura",
    "key biscayne": "Key Biscayne",
    "bal harbour": "Bal Harbour",
    "bal harbor": "Bal Harbour",
    "south beach": "South Beach",
    "miami beach": "Miami Beach",
    "mid-beach": "Mid-Beach",
    "mid beach": "Mid-Beach",
    "north beach": "North Beach",
    "north miami": "North Miami",
    "edgewater": "Edgewater",
    "doral": "Doral",
    "wynwood": "Wynwood",
}

# Distinct property_type values in the CSV
PROPERTY_TYPES: list[str] = ["Condo", "Multi-Family", "Single Family", "Townhouse", "Villa"]

# Buyer phrasing -> canonical property_type
PROPERTY_TYPE_ALIASES: dict[str, str] = {
    "condo": "Condo",
    "condominium": "Condo",
    "apartment": "Condo",
    "starter condo": "Condo",
    "townhouse": "Townhouse",
    "town home": "Townhouse",
    "townhome": "Townhouse",
    "single family": "Single Family",
    "single-family": "Single Family",
    "house": "Single Family",
    "home": "Single Family",
    "villa": "Villa",
    "multi-family": "Multi-Family",
    "multifamily": "Multi-Family",
    "duplex": "Multi-Family",
}

# Distinct feature tokens that appear in the semicolon-separated `features` field
KNOWN_FEATURES: list[str] = [
    "Bay View", "Pool", "Concierge", "Rooftop", "Balcony", "Gym", "Waterfront",
    "Tennis Court", "Hardwood Floors", "High Ceilings", "Boat Dock", "Garage",
    "Private Beach Access", "Pet Friendly", "Walk-in Closet", "Smart Home",
    "Terrace", "Gated Community", "Stainless Steel Appliances", "Wine Cellar",
    "Garden", "Marble Floors", "Ocean View", "Doorman", "Home Office",
    "Updated Kitchen", "Granite Countertops", "Hurricane Impact Windows",
    "Solar Panels", "Central AC", "Modern Kitchen", "Large Lot",
]

# Buyer phrasing -> the MLS feature token(s) it should map to.
# Keys are matched as lowercase substrings of the inquiry.
FEATURE_SYNONYMS: dict[str, list[str]] = {
    "pool": ["Pool"],
    "gym": ["Gym"],
    "fitness": ["Gym"],
    "balcony": ["Balcony"],
    "terrace": ["Terrace"],
    "rooftop": ["Rooftop"],
    "waterfront": ["Waterfront"],
    "ocean view": ["Ocean View"],
    "ocean": ["Ocean View"],
    "bay view": ["Bay View"],
    "water view": ["Waterfront", "Bay View", "Ocean View"],
    "boat dock": ["Boat Dock"],
    "dock": ["Boat Dock"],
    "boat": ["Boat Dock"],
    "garage": ["Garage"],
    "pet friendly": ["Pet Friendly"],
    "pet-friendly": ["Pet Friendly"],
    "pets": ["Pet Friendly"],
    "cat": ["Pet Friendly"],
    "dog": ["Pet Friendly"],
    "home office": ["Home Office"],
    "office": ["Home Office"],
    "updated kitchen": ["Updated Kitchen"],
    "modern kitchen": ["Modern Kitchen", "Updated Kitchen"],
    "concierge": ["Concierge"],
    "doorman": ["Doorman"],
    "gated": ["Gated Community"],
    "gated community": ["Gated Community"],
    "smart home": ["Smart Home"],
    "wine cellar": ["Wine Cellar"],
    "garden": ["Garden"],
    "private beach": ["Private Beach Access"],
    "beach access": ["Private Beach Access"],
    "tennis": ["Tennis Court"],
    "hurricane": ["Hurricane Impact Windows"],
    "solar": ["Solar Panels"],
    "hardwood": ["Hardwood Floors"],
    "high ceilings": ["High Ceilings"],
    "walk-in closet": ["Walk-in Closet"],
    "central ac": ["Central AC"],
    "air conditioning": ["Central AC"],
}

# Wants that buyers express but which have NO clean MLS field. The agent must
# match these approximately (or not at all) and say so honestly in the brief.
# phrase substring -> human explanation of the limitation
UNMATCHABLE_WANTS: dict[str, str] = {
    "good school": "School quality is not in the MLS feed; verify against GreatSchools/district data.",
    "schools matter": "School quality is not in the MLS feed; verify against GreatSchools/district data.",
    "elementary school": "School assignment is not in the MLS feed; confirm zoning with the district.",
    "near pharmacy": "Proximity to pharmacies is not an MLS field; verify via maps before the call.",
    "pharmacy": "Proximity to pharmacies is not an MLS field; verify via maps before the call.",
    "near grocery": "Proximity to grocery is not an MLS field; verify via maps before the call.",
    "grocery": "Proximity to grocery is not an MLS field; verify via maps before the call.",
    "medical": "Proximity to medical facilities is not an MLS field; verify via maps before the call.",
    "single-story": "Single-story / number-of-floors is not a structured MLS field here; confirm with listing agent.",
    "single story": "Single-story / number-of-floors is not a structured MLS field here; confirm with listing agent.",
    "elevator": "Elevator access is not a structured MLS field here; confirm with the listing agent / building.",
    "city view": "There is no 'City View' feature in this feed (only Ocean/Bay/Waterfront); treat as approximate.",
    "don't drive": "Walkability / transit access is not in the MLS feed; verify via maps.",
    "commute": "Commute time is not in the MLS feed; verify drive time to the buyer's work location.",
    "parking spot": "Number of parking spaces is not structured here (only 'Garage' yes/no); confirm count with listing agent.",
    "needing some work": "Renovation condition / cap-rate is not in the MLS feed; requires a financial workup.",
    "cash-flowing": "Rental income / cap-rate is not in the MLS feed; requires a rent-roll / pro-forma.",
}

# Phrases that signal a request only a human (the realtor) should answer.
HUMAN_JUDGMENT_TRIGGERS: dict[str, str] = {
    "offer": "Buyer is asking about offer price / strategy - a licensed-realtor judgment call.",
    "go lower": "Buyer is asking about negotiation strategy - escalate to the realtor.",
    "negotiat": "Buyer is asking about negotiation - escalate to the realtor.",
    "seller": "Buyer is asking about seller motivation - not in our data; the realtor must assess.",
    "motivation": "Buyer is asking about seller motivation - not in our data; the realtor must assess.",
    "what do you think": "Buyer is asking for advice/opinion - better coming from the realtor.",
    "should i": "Buyer is asking for a recommendation - escalate to the realtor.",
}
