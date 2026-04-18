from __future__ import annotations

import json
from typing import Any

import httpx

from leadflow.config import Settings


class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _request_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._settings.openai_model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return json.loads(content)

    def plan_prompt(self, raw_prompt: str, requested_limit: int) -> dict[str, Any]:
        system_prompt = (
            "You convert natural-language lead generation requests into structured JSON for a LinkedIn-first outbound workflow. "
            "Return only JSON with keys: target_roles, industries, geographies, seniority_hints, exclusions, outreach_angle, result_limit."
        )
        user_prompt = (
            f"User prompt:\n{raw_prompt}\n\n"
            f"Preferred result limit: {requested_limit}\n"
            "Infer sensible search structure for B2B prospecting. Use arrays for list fields."
        )
        return self._request_json(system_prompt=system_prompt, user_prompt=user_prompt)

    def score_prospect(self, brief: dict[str, Any], prospect: dict[str, Any]) -> dict[str, Any]:
        system_prompt = (
            "You score sales prospects for fit against a search brief. "
            "Return only JSON with keys: ai_decision, confidence_score, score_reason. "
            "ai_decision must be target, review, or reject. confidence_score must be 0-100."
        )
        user_prompt = (
            "Search brief:\n"
            f"{json.dumps(brief, indent=2)}\n\n"
            "Prospect:\n"
            f"{json.dumps(prospect, indent=2, default=str)}\n\n"
            "Score this prospect for outbound relevance and keep the reason to one sentence."
        )
        return self._request_json(system_prompt=system_prompt, user_prompt=user_prompt)
