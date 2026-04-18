from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PromptCreateRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=4000)
    requested_limit: int = Field(default=5, ge=1, le=100)


class PromptResponse(BaseModel):
    id: str
    raw_prompt: str
    canonical_brief_json: dict[str, Any]
    status: str
    requested_limit: int
    discovered_count: int
    scored_count: int
    enriched_count: int
    error_text: str | None
    created_at: datetime
    updated_at: datetime


class ProspectSummaryResponse(BaseModel):
    id: str
    prompt_prospect_id: str
    source_rank: int
    ai_decision: str | None
    confidence_score: int
    score_reason: str | None
    enrichment_status: str
    best_phone_e164: str | None
    phones_json: list[Any]
    voicecall_call_id: str | None
    last_called_at: datetime | None
    profile_url: str
    full_name: str | None
    headline: str | None
    job_title: str | None
    company_name: str | None
    company_domain: str | None
    location: str | None
    created_at: datetime
    updated_at: datetime


class PromptListResponse(BaseModel):
    items: list[PromptResponse]


class ProspectListResponse(BaseModel):
    items: list[ProspectSummaryResponse]


class CallResultResponse(BaseModel):
    prompt_prospect_id: str
    voicecall_call_id: str
    status: str
