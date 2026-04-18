from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from leadflow.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class PromptStatus(StrEnum):
    queued = "queued"
    planning = "planning"
    discovering = "discovering"
    scoring = "scoring"
    enriching = "enriching"
    ready = "ready"
    partial = "partial"
    failed = "failed"


class ProspectDecision(StrEnum):
    target = "target"
    review = "review"
    reject = "reject"


class EnrichmentStatus(StrEnum):
    pending = "pending"
    skipped = "skipped"
    complete = "complete"
    failed = "failed"


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    raw_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_brief_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default=PromptStatus.queued, nullable=False)
    requested_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scored_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enriched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    prompt_prospects: Mapped[list["PromptProspect"]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="desc(PromptProspect.confidence_score), PromptProspect.source_rank",
    )


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    profile_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    prompt_prospects: Mapped[list["PromptProspect"]] = relationship(back_populates="prospect")


class PromptProspect(Base):
    __tablename__ = "prompt_prospects"
    __table_args__ = (UniqueConstraint("prompt_id", "prospect_id", name="uq_prompt_prospect"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True)
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(String(24), default=EnrichmentStatus.pending, nullable=False)
    best_phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phones_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    voicecall_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    prompt: Mapped[Prompt] = relationship(back_populates="prompt_prospects")
    prospect: Mapped[Prospect] = relationship(back_populates="prompt_prospects")
