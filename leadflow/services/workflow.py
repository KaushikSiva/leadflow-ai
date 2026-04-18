from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from sqlalchemy.orm import Session

from leadflow.config import Settings
from leadflow.db.models import EnrichmentStatus, Prompt, PromptProspect, PromptStatus
from leadflow.integrations.apify_client import ApifyClient
from leadflow.integrations.openai_client import OpenAIClient
from leadflow.integrations.voicecall_client import VoiceCallClient
from leadflow import repositories
from leadflow.services.normalize import (
    choose_best_phone,
    collapse_ws,
    extract_phone_candidates,
    normalize_phone,
    normalize_prompt_brief,
    normalize_prospect_payload,
    normalize_score_payload,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    settings: Settings
    openai: OpenAIClient
    apify: ApifyClient
    voicecall: VoiceCallClient


def build_context(settings: Settings) -> WorkflowContext:
    return WorkflowContext(
        settings=settings,
        openai=OpenAIClient(settings),
        apify=ApifyClient(settings),
        voicecall=VoiceCallClient(settings),
    )


def serialize_prompt(prompt: Prompt) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "raw_prompt": prompt.raw_prompt,
        "canonical_brief_json": prompt.canonical_brief_json or {},
        "status": prompt.status,
        "requested_limit": prompt.requested_limit,
        "discovered_count": prompt.discovered_count,
        "scored_count": prompt.scored_count,
        "enriched_count": prompt.enriched_count,
        "error_text": prompt.error_text,
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }


def serialize_prompt_prospect(item: PromptProspect) -> dict[str, Any]:
    prospect = item.prospect
    return {
        "id": prospect.id,
        "prompt_prospect_id": item.id,
        "source_rank": item.source_rank,
        "ai_decision": item.ai_decision,
        "confidence_score": item.confidence_score,
        "score_reason": item.score_reason,
        "enrichment_status": item.enrichment_status,
        "best_phone_e164": item.best_phone_e164,
        "phones_json": item.phones_json or [],
        "voicecall_call_id": item.voicecall_call_id,
        "last_called_at": item.last_called_at,
        "profile_url": prospect.profile_url,
        "full_name": prospect.full_name,
        "headline": prospect.headline,
        "job_title": prospect.job_title,
        "company_name": prospect.company_name,
        "company_domain": prospect.company_domain,
        "location": prospect.location,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def build_call_payload(prompt: Prompt, item: PromptProspect, settings: Settings) -> dict[str, Any]:
    prospect = item.prospect
    phones = item.phones_json or []
    phones_text = ", ".join(str(phone) for phone in phones[:3]) if phones else "No enriched phone on file"
    destination_number = normalize_phone(settings.voicecall_destination_number) or settings.voicecall_destination_number
    company_bits = [collapse_ws(prospect.company_name), collapse_ws(prospect.job_title), collapse_ws(prospect.location)]
    company_context = ", ".join(bit for bit in company_bits if bit)
    objective = collapse_ws(
        f"Reach out about {prompt.canonical_brief_json.get('outreach_angle') or 'the active prospecting brief'} for "
        f"{prospect.full_name or 'this lead'} at {prospect.company_name or 'their company'}."
    )
    talking_points_parts = [
        company_context,
        collapse_ws(f"Confidence {item.confidence_score}/100."),
        collapse_ws(item.score_reason),
        collapse_ws(f"Enriched phones: {phones_text}."),
        collapse_ws(f"Original search prompt: {prompt.raw_prompt}"),
    ]
    payload: dict[str, Any] = {
        "to": destination_number,
        "context": {
            "objective": objective,
            "talking_points": " ".join(part for part in talking_points_parts if part),
        },
        "metadata": {
            "prompt_id": prompt.id,
            "prompt_prospect_id": item.id,
            "profile_url": prospect.profile_url,
        },
    }
    if settings.voicecall_from_number:
        payload["from"] = settings.voicecall_from_number
    return payload


def place_prospect_call(db: Session, item: PromptProspect, workflow: WorkflowContext) -> dict[str, Any]:
    payload = build_call_payload(item.prompt, item, workflow.settings)
    response = workflow.voicecall.create_call(payload)
    repositories.mark_prompt_prospect_called(db, item, response["call_id"])
    return response


def process_prompt(db: Session, prompt: Prompt, workflow: WorkflowContext) -> Prompt:
    errors: list[str] = []
    logger.info("prompt=%s stage=planning start", prompt.id)

    try:
        planned = workflow.openai.plan_prompt(prompt.raw_prompt, prompt.requested_limit)
        brief = normalize_prompt_brief(planned, prompt.requested_limit)
    except Exception as exc:
        logger.exception("prompt=%s stage=planning failed", prompt.id)
        repositories.update_prompt_status(db, prompt, PromptStatus.failed, f"Planning failed: {exc}")
        return prompt

    prompt = repositories.save_prompt_brief(db, prompt, brief)
    logger.info(
        "prompt=%s stage=planning done limit=%s roles=%s geographies=%s",
        prompt.id,
        brief.get("result_limit"),
        len(brief.get("target_roles", [])),
        len(brief.get("geographies", [])),
    )

    try:
        repositories.update_prompt_status(db, prompt, PromptStatus.discovering)
        logger.info("prompt=%s stage=discovering start", prompt.id)
        discovered = workflow.apify.discover_profiles(brief)
    except Exception as exc:
        logger.exception("prompt=%s stage=discovering failed", prompt.id)
        repositories.update_prompt_status(db, prompt, PromptStatus.failed, f"Discovery failed: {exc}")
        return prompt

    logger.info("prompt=%s stage=discovering raw_count=%s", prompt.id, len(discovered))
    attached: list[PromptProspect] = []
    for index, raw_item in enumerate(discovered, start=1):
        normalized = normalize_prospect_payload(raw_item, workflow.settings.apify_profile_actor_id)
        if not normalized:
            continue
        prospect = repositories.upsert_prospect(db, normalized)
        attached.append(repositories.attach_prompt_prospect(db, prompt.id, prospect.id, index))

    prompt = repositories.set_prompt_counts(db, prompt, discovered=len(attached))
    logger.info("prompt=%s stage=discovering done normalized_count=%s", prompt.id, len(attached))

    repositories.update_prompt_status(db, prompt, PromptStatus.scoring)
    logger.info("prompt=%s stage=scoring start prospects=%s", prompt.id, len(attached))
    scored_count = 0
    scoring_items = repositories.list_prompt_prospects(db, prompt.id)
    for index, item in enumerate(scoring_items, start=1):
        scored_count += 1
        prospect_payload = serialize_prompt_prospect(item)
        logger.info(
            "prompt=%s stage=scoring profile=%s/%s url=%s start",
            prompt.id,
            index,
            len(scoring_items),
            item.prospect.profile_url,
        )
        try:
            raw_score = workflow.openai.score_prospect(brief, prospect_payload)
            score = normalize_score_payload(raw_score)
            repositories.update_prompt_prospect_score(db, item, **score)
            logger.info(
                "prompt=%s stage=scoring profile=%s/%s url=%s done decision=%s score=%s",
                prompt.id,
                index,
                len(scoring_items),
                item.prospect.profile_url,
                score["ai_decision"],
                score["confidence_score"],
            )
        except Exception as exc:
            repositories.update_prompt_prospect_score(
                db,
                item,
                ai_decision="reject",
                confidence_score=0,
                score_reason=f"Scoring failed: {exc}",
            )
            errors.append(f"Scoring failed for {item.prospect.profile_url}: {exc}")
            logger.exception(
                "prompt=%s stage=scoring profile=%s/%s url=%s failed",
                prompt.id,
                index,
                len(scoring_items),
                item.prospect.profile_url,
            )
    prompt = repositories.set_prompt_counts(db, prompt, scored=scored_count)
    logger.info(
        "prompt=%s stage=scoring done scored=%s errors=%s",
        prompt.id,
        scored_count,
        sum(1 for error in errors if error.startswith("Scoring failed")),
    )

    repositories.update_prompt_status(db, prompt, PromptStatus.enriching)
    logger.info("prompt=%s stage=enriching start prospects=%s", prompt.id, scored_count)
    enriched_count = 0
    enrichment_items = repositories.list_prompt_prospects(db, prompt.id)
    for index, item in enumerate(enrichment_items, start=1):
        logger.info(
            "prompt=%s stage=enriching profile=%s/%s url=%s start",
            prompt.id,
            index,
            len(enrichment_items),
            item.prospect.profile_url,
        )
        try:
            result = workflow.apify.enrich_phones(serialize_prompt_prospect(item))
            phones = extract_phone_candidates(result)
            best_phone = choose_best_phone(phones)
            repositories.update_prompt_prospect_enrichment(
                db,
                item,
                enrichment_status=EnrichmentStatus.complete,
                phones_json=phones,
                best_phone_e164=best_phone,
            )
            enriched_count += 1
            logger.info(
                "prompt=%s stage=enriching profile=%s/%s url=%s done phones=%s best_phone=%s",
                prompt.id,
                index,
                len(enrichment_items),
                item.prospect.profile_url,
                len(phones),
                best_phone or "-",
            )
        except Exception as exc:
            repositories.update_prompt_prospect_enrichment(
                db,
                item,
                enrichment_status=EnrichmentStatus.failed,
                phones_json=[],
                best_phone_e164=None,
            )
            errors.append(f"Enrichment failed for {item.prospect.profile_url}: {exc}")
            logger.exception(
                "prompt=%s stage=enriching profile=%s/%s url=%s failed",
                prompt.id,
                index,
                len(enrichment_items),
                item.prospect.profile_url,
            )

    prompt = repositories.set_prompt_counts(db, prompt, enriched=enriched_count)
    final_status = PromptStatus.ready if not errors else PromptStatus.partial
    repositories.update_prompt_status(db, prompt, final_status, "\n".join(errors) if errors else None)
    logger.info(
        "prompt=%s stage=enriching done enriched=%s errors=%s final_status=%s",
        prompt.id,
        enriched_count,
        len(errors),
        final_status,
    )
    return prompt
