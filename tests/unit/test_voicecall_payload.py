from __future__ import annotations

from leadflow.config import get_settings
from leadflow.db.models import Prompt, PromptProspect, Prospect
from leadflow.services.workflow import build_call_payload


def test_voicecall_payload_always_uses_hardcoded_destination(monkeypatch) -> None:
    monkeypatch.setenv("VOICECALL_DESTINATION_NUMBER", "214-909-8059")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./unit.db")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APIFY_API_TOKEN", "test")
    monkeypatch.setenv("APIFY_PROFILE_ACTOR_ID", "profile-actor")
    monkeypatch.setenv("APIFY_PHONE_ENRICH_ACTOR_ID", "phone-actor")
    monkeypatch.setenv("VOICECALL_API_BASE_URL", "http://voicecall")
    monkeypatch.setenv("VOICECALL_API_TOKEN", "secret")
    get_settings.cache_clear()
    settings = get_settings()

    prompt = Prompt(id="prompt-1", raw_prompt="Find HVAC owners", canonical_brief_json={"outreach_angle": "lead gen help"}, status="ready", requested_limit=10)
    prospect = Prospect(
        id="prospect-1",
        profile_url="https://linkedin.com/in/jane",
        full_name="Jane",
        job_title="Founder",
        company_name="Northwind",
        company_domain="northwind.com",
        location="Dallas",
        source_payload_json={},
    )
    item = PromptProspect(
        id="pp-1",
        prompt=prompt,
        prospect=prospect,
        confidence_score=82,
        score_reason="High-fit founder in target geography.",
        phones_json=["+12149098059"],
    )

    payload = build_call_payload(prompt, item, settings)

    assert payload["to"] == "214-909-8059"
    assert "customer_name" not in payload["context"]
    assert payload["metadata"]["prompt_id"] == "prompt-1"
    assert payload["metadata"]["prompt_prospect_id"] == "pp-1"

