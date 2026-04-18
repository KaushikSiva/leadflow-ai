from __future__ import annotations

from typing import Any

import httpx

from leadflow.config import Settings


class VoiceCallClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self._settings.voicecall_api_base_url.rstrip('/')}/v1/calls/outbound",
            headers={
                "Authorization": f"Bearer {self._settings.voicecall_api_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45.0,
        )
        response.raise_for_status()
        return response.json()

