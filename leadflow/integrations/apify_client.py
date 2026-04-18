from __future__ import annotations

import math
from typing import Any

import httpx

from leadflow.config import Settings


class ApifyClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = "https://api.apify.com/v2/acts"

    @staticmethod
    def _normalize_actor_id(actor_id: str) -> str:
        actor = actor_id.strip()
        if "/" in actor and "~" not in actor:
            owner, name = actor.split("/", 1)
            return f"{owner}~{name}"
        return actor

    def _run_actor(self, actor_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_actor_id = self._normalize_actor_id(actor_id)
        response = httpx.post(
            f"{self._base_url}/{normalized_actor_id}/run-sync-get-dataset-items",
            params={"token": self._settings.apify_api_token},
            json=payload,
            timeout=self._settings.apify_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    def build_discovery_payload(self, brief: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        actor_id = self._settings.apify_profile_actor_id
        normalized_actor_id = self._normalize_actor_id(actor_id)
        result_limit = int(brief.get("result_limit", 25) or 25)

        if normalized_actor_id == "harvestapi~linkedin-profile-search":
            payload = {
                "profileScraperMode": "Short",
                "searchQuery": "",
                "currentJobTitles": list(brief.get("target_roles", []))[:50],
                "locations": list(brief.get("geographies", []))[:70],
                "maxItems": result_limit,
                "takePages": max(1, min(100, math.ceil(result_limit / 25))),
            }
        else:
            payload = {
                "query": {
                    "roles": brief.get("target_roles", []),
                    "industries": brief.get("industries", []),
                    "geographies": brief.get("geographies", []),
                    "seniorityHints": brief.get("seniority_hints", []),
                    "exclusions": brief.get("exclusions", []),
                    "outreachAngle": brief.get("outreach_angle", ""),
                },
                "limit": result_limit,
            }
        return actor_id, payload

    def discover_profiles(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        actor_id, payload = self.build_discovery_payload(brief)
        return self._run_actor(actor_id, payload)

    def enrich_phones(self, prospect: dict[str, Any]) -> list[dict[str, Any]]:
        payload = {
            "profileUrl": prospect.get("profile_url"),
            "fullName": prospect.get("full_name"),
            "companyName": prospect.get("company_name"),
            "companyDomain": prospect.get("company_domain"),
            "jobTitle": prospect.get("job_title"),
        }
        return self._run_actor(self._settings.apify_phone_enrich_actor_id, payload)
