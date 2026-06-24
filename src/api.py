"""JSON API layer over the agent.

  POST /inquiry  -> JSON API: raw inquiry in, Lead Brief JSON out
  GET  /health   -> runtime info
  GET  /docs     -> auto Swagger

The HTML UI has moved to streamlit_app.py (run with: streamlit run streamlit_app.py).
Every path calls the SAME run_agent() as the batch runner and Streamlit UI.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .agent import run_agent, runtime_info
from .models import Inquiry, LeadBrief

app = FastAPI(
    title="AgentMira - Buyer Lead Intake Agent",
    description="Paste a free-text buyer inquiry; get a realtor-ready Lead Brief.",
    version="1.0.0",
)


class InquiryIn(BaseModel):
    """The website_form shape (only `message` is required)."""
    message: str
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    buyer_phone: Optional[str] = None
    channel: str = "website_form"
    lead_id: str = "AD-HOC"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **runtime_info()}


@app.post("/inquiry", response_model=LeadBrief)
def inquiry_api(payload: InquiryIn) -> LeadBrief:
    """JSON API - same agent code path as the batch runner and Streamlit UI."""
    return run_agent(Inquiry(**payload.model_dump()))
