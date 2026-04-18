from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session, joinedload

from leadflow.db.models import EnrichmentStatus, Prompt, PromptProspect, PromptStatus, Prospect


def create_prompt(db: Session, raw_prompt: str, requested_limit: int) -> Prompt:
    prompt = Prompt(raw_prompt=raw_prompt, requested_limit=requested_limit, status=PromptStatus.queued)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def list_prompts(db: Session, limit: int = 20) -> list[Prompt]:
    stmt = select(Prompt).order_by(Prompt.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def get_prompt(db: Session, prompt_id: str) -> Prompt | None:
    return db.get(Prompt, prompt_id)


def lease_next_prompt(db: Session) -> Prompt | None:
    stmt = (
        select(Prompt)
        .where(Prompt.status == PromptStatus.queued)
        .order_by(Prompt.created_at.asc())
        .limit(1)
    )
    prompt = db.scalar(stmt)
    if not prompt:
        return None
    prompt.status = PromptStatus.planning
    prompt.error_text = None
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def update_prompt_status(db: Session, prompt: Prompt, status: str, error_text: str | None = None) -> Prompt:
    prompt.status = status
    prompt.error_text = error_text
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def save_prompt_brief(db: Session, prompt: Prompt, brief: dict) -> Prompt:
    prompt.canonical_brief_json = brief
    prompt.requested_limit = int(brief.get("result_limit") or prompt.requested_limit)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def reset_prompt_for_retry(db: Session, prompt: Prompt) -> Prompt:
    db.execute(delete(PromptProspect).where(PromptProspect.prompt_id == prompt.id))
    prompt.status = PromptStatus.queued
    prompt.discovered_count = 0
    prompt.scored_count = 0
    prompt.enriched_count = 0
    prompt.error_text = None
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def upsert_prospect(db: Session, payload: dict) -> Prospect:
    stmt = select(Prospect).where(Prospect.profile_url == payload["profile_url"])
    prospect = db.scalar(stmt)
    if not prospect:
        prospect = Prospect(**payload)
    else:
        for field, value in payload.items():
            if value not in (None, "", [], {}):
                setattr(prospect, field, value)
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


def attach_prompt_prospect(db: Session, prompt_id: str, prospect_id: str, source_rank: int) -> PromptProspect:
    stmt = select(PromptProspect).where(
        PromptProspect.prompt_id == prompt_id,
        PromptProspect.prospect_id == prospect_id,
    )
    existing = db.scalar(stmt)
    if existing:
        existing.source_rank = source_rank
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    item = PromptProspect(
        prompt_id=prompt_id,
        prospect_id=prospect_id,
        source_rank=source_rank,
        enrichment_status=EnrichmentStatus.pending,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_prompt_prospects(db: Session, prompt_id: str) -> list[PromptProspect]:
    stmt = (
        select(PromptProspect)
        .where(PromptProspect.prompt_id == prompt_id)
        .options(joinedload(PromptProspect.prospect))
        .order_by(desc(PromptProspect.confidence_score), PromptProspect.source_rank.asc())
    )
    return list(db.scalars(stmt).all())


def get_prompt_prospect(db: Session, prompt_prospect_id: str) -> PromptProspect | None:
    stmt = (
        select(PromptProspect)
        .where(PromptProspect.id == prompt_prospect_id)
        .options(joinedload(PromptProspect.prospect), joinedload(PromptProspect.prompt))
    )
    return db.scalar(stmt)


def set_prompt_counts(db: Session, prompt: Prompt, *, discovered: int | None = None, scored: int | None = None, enriched: int | None = None) -> Prompt:
    if discovered is not None:
        prompt.discovered_count = discovered
    if scored is not None:
        prompt.scored_count = scored
    if enriched is not None:
        prompt.enriched_count = enriched
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def update_prompt_prospect_score(
    db: Session,
    item: PromptProspect,
    *,
    ai_decision: str,
    confidence_score: int,
    score_reason: str,
) -> PromptProspect:
    item.ai_decision = ai_decision
    item.confidence_score = confidence_score
    item.score_reason = score_reason
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_prompt_prospect_enrichment(
    db: Session,
    item: PromptProspect,
    *,
    enrichment_status: str,
    phones_json: list,
    best_phone_e164: str | None,
) -> PromptProspect:
    item.enrichment_status = enrichment_status
    item.phones_json = phones_json
    item.best_phone_e164 = best_phone_e164
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def set_prompt_prospect_enrichment_status(db: Session, item: PromptProspect, status: str) -> PromptProspect:
    item.enrichment_status = status
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def mark_prompt_prospect_called(db: Session, item: PromptProspect, voicecall_call_id: str) -> PromptProspect:
    item.voicecall_call_id = voicecall_call_id
    item.last_called_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
