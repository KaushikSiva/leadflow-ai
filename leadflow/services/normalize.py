from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse


def collapse_ws(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def ensure_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        parts = [chunk.strip() for chunk in re.split(r"[,;\n]", value) if chunk.strip()]
        return parts if parts else [value.strip()]
    if isinstance(value, Iterable):
        items = [collapse_ws(item) for item in value if collapse_ws(item)]
        return items
    return [collapse_ws(value)] if collapse_ws(value) else []


def extract_domain(value: Any) -> str | None:
    text = collapse_ws(value)
    if not text:
        return None
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or parsed.path).lower().strip()
    host = re.sub(r"^www\.", "", host)
    return host or None


def normalize_profile_url(value: Any) -> str | None:
    text = collapse_ws(value)
    if not text:
        return None
    if text.startswith("www."):
        text = f"https://{text}"
    if "://" not in text:
        text = f"https://{text}"
    return text.rstrip("/")


def normalize_phone(value: Any) -> str | None:
    text = collapse_ws(value)
    if not text:
        return None

    if text.startswith("+"):
        digits = "+" + re.sub(r"\D", "", text)
        return digits if 8 <= len(digits[1:]) <= 15 else None

    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def choose_best_phone(phones: list[str]) -> str | None:
    normalized = []
    for phone in phones:
        candidate = normalize_phone(phone)
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized[0] if normalized else None


def _walk_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
        return
    yield value


def extract_phone_candidates(payload: Any) -> list[str]:
    seen: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = key.lower()
            if any(token in lowered for token in ("phone", "mobile", "cell", "telephone", "tel")):
                for item in _walk_values(value):
                    candidate = normalize_phone(item)
                    if candidate and candidate not in seen:
                        seen.append(candidate)
    for item in _walk_values(payload):
        candidate = normalize_phone(item)
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


def normalize_prompt_brief(raw_brief: dict[str, Any], default_limit: int) -> dict[str, Any]:
    limit = raw_brief.get("result_limit", default_limit)
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = default_limit
    limit_value = min(max(limit_value, 1), 100)

    return {
        "target_roles": ensure_list(raw_brief.get("target_roles")),
        "industries": ensure_list(raw_brief.get("industries")),
        "geographies": ensure_list(raw_brief.get("geographies")),
        "seniority_hints": ensure_list(raw_brief.get("seniority_hints")),
        "exclusions": ensure_list(raw_brief.get("exclusions")),
        "outreach_angle": collapse_ws(raw_brief.get("outreach_angle")),
        "result_limit": limit_value,
    }


def score_band(score: int) -> str:
    if score >= 60:
        return "target"
    if score >= 40:
        return "review"
    return "reject"


def normalize_score_payload(raw_score: dict[str, Any]) -> dict[str, Any]:
    try:
        score = int(raw_score.get("confidence_score", 0))
    except (TypeError, ValueError):
        score = 0
    score = min(max(score, 0), 100)

    decision = collapse_ws(raw_score.get("ai_decision")).lower()
    if decision not in {"target", "review", "reject"}:
        decision = score_band(score)

    reason = collapse_ws(raw_score.get("score_reason")) or "No rationale returned."
    return {"ai_decision": decision, "confidence_score": score, "score_reason": reason}


def normalize_prospect_payload(raw_item: dict[str, Any], source_actor: str) -> dict[str, Any] | None:
    profile_url = normalize_profile_url(
        first_value(
            raw_item,
            "profileUrl",
            "profile_url",
            "linkedinUrl",
            "linkedin_url",
            "url",
            "link",
        )
    )
    if not profile_url:
        return None

    current_positions = raw_item.get("currentPositions")
    primary_position = current_positions[0] if isinstance(current_positions, list) and current_positions else {}
    company_website = first_value(
        raw_item,
        "companyWebsite",
        "company_website",
        "website",
        *(["companyLinkedinUrl"] if isinstance(primary_position, dict) else []),
    )
    company_domain = extract_domain(first_value(raw_item, "companyDomain", "company_domain", "domain")) or extract_domain(
        company_website
    )
    full_name = collapse_ws(first_value(raw_item, "fullName", "full_name", "name")) or None
    if not full_name:
        first_name = collapse_ws(first_value(raw_item, "firstName", "first_name"))
        last_name = collapse_ws(first_value(raw_item, "lastName", "last_name"))
        full_name = " ".join(part for part in [first_name, last_name] if part) or None

    location_value = first_value(raw_item, "location", "geo", "city")
    if isinstance(location_value, dict):
        location_value = first_value(location_value, "linkedinText", "text", "name")

    return {
        "profile_url": profile_url,
        "full_name": full_name,
        "headline": collapse_ws(first_value(raw_item, "headline", "summary", "about")) or None,
        "job_title": collapse_ws(
            first_value(raw_item, "jobTitle", "job_title", "title", "position")
            or (primary_position.get("title") if isinstance(primary_position, dict) else None)
        )
        or None,
        "company_name": collapse_ws(
            first_value(raw_item, "companyName", "company_name", "company")
            or (primary_position.get("companyName") if isinstance(primary_position, dict) else None)
        )
        or None,
        "company_domain": company_domain,
        "location": collapse_ws(location_value) or None,
        "source_actor": source_actor,
        "source_payload_json": raw_item,
    }
