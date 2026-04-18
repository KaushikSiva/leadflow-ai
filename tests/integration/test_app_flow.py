from __future__ import annotations

import json
from dataclasses import dataclass

from leadflow.api.app import create_app
from leadflow.db.session import SessionLocal
from leadflow import repositories
from leadflow.services.workflow import WorkflowContext, process_prompt


class FakeOpenAI:
    def __init__(self, *, fail_score_on: str | None = None) -> None:
        self.fail_score_on = fail_score_on

    def plan_prompt(self, raw_prompt: str, requested_limit: int) -> dict:
        return {
            "target_roles": ["Owner"],
            "industries": ["HVAC"],
            "geographies": ["Dallas"],
            "seniority_hints": ["Founder"],
            "exclusions": [],
            "outreach_angle": "lead generation help",
            "result_limit": requested_limit,
        }

    def score_prospect(self, brief: dict, prospect: dict) -> dict:
        if self.fail_score_on and self.fail_score_on in prospect["profile_url"]:
            raise ValueError("malformed score output")
        if "alpha" in prospect["profile_url"]:
            return {"ai_decision": "target", "confidence_score": 84, "score_reason": "High-fit owner in target market."}
        return {"ai_decision": "review", "confidence_score": 55, "score_reason": "Some fit but weaker signal."}


class FakeApify:
    def __init__(self, *, fail_enrich: bool = False, fail_discovery: bool = False) -> None:
        self.fail_enrich = fail_enrich
        self.fail_discovery = fail_discovery

    def discover_profiles(self, brief: dict) -> list[dict]:
        if self.fail_discovery:
            raise RuntimeError("actor unavailable")
        return [
            {
                "profileUrl": "https://linkedin.com/in/alpha-owner",
                "fullName": "Alex Alpha",
                "title": "Owner",
                "companyName": "Alpha Air",
                "companyWebsite": "https://alphaair.com",
                "location": "Dallas, TX",
            },
            {
                "profileUrl": "https://linkedin.com/in/beta-owner",
                "fullName": "Blake Beta",
                "title": "Owner",
                "companyName": "Beta Cooling",
                "companyWebsite": "https://betacooling.com",
                "location": "Dallas, TX",
            },
        ]

    def enrich_phones(self, prospect: dict) -> list[dict]:
        if self.fail_enrich:
            raise TimeoutError("enrichment timeout")
        return [{"mobilePhone": "(214) 909-8059"}]


class FakeVoiceCall:
    def create_call(self, payload: dict) -> dict:
        return {"call_id": "call-123", "status": "dialing"}


@dataclass
class FakeSettings:
    voicecall_destination_number: str = "214-909-8059"
    voicecall_from_number: str | None = None
    apify_profile_actor_id: str = "profile-actor"


def build_workflow(*, fail_score_on: str | None = None, fail_enrich: bool = False, fail_discovery: bool = False) -> WorkflowContext:
    return WorkflowContext(
        settings=FakeSettings(),
        openai=FakeOpenAI(fail_score_on=fail_score_on),
        apify=FakeApify(fail_enrich=fail_enrich, fail_discovery=fail_discovery),
        voicecall=FakeVoiceCall(),
    )


def test_happy_path_processes_prompt_and_places_call(test_db, monkeypatch) -> None:
    app = create_app()
    client = app.test_client()

    create_response = client.post(
        "/api/prompts",
        data=json.dumps({"prompt": "Find HVAC company owners in Dallas", "requested_limit": 10}),
        content_type="application/json",
    )
    assert create_response.status_code == 200
    prompt_id = create_response.get_json()["id"]

    with SessionLocal() as db:
        prompt = repositories.get_prompt(db, prompt_id)
        process_prompt(db, prompt, build_workflow())

    monkeypatch.setattr("leadflow.api.app.build_context", lambda settings: build_workflow())

    prompt_response = client.get(f"/api/prompts/{prompt_id}")
    assert prompt_response.status_code == 200
    assert prompt_response.get_json()["status"] == "ready"

    prospects_response = client.get(f"/api/prompts/{prompt_id}/prospects")
    items = prospects_response.get_json()["items"]
    assert items[0]["confidence_score"] >= items[1]["confidence_score"]
    assert items[0]["best_phone_e164"] == "+12149098059"

    call_response = client.post(f"/api/prompt-prospects/{items[0]['prompt_prospect_id']}/call")
    assert call_response.status_code == 200
    assert call_response.get_json()["voicecall_call_id"] == "call-123"

    with SessionLocal() as db:
        stored = repositories.get_prompt_prospect(db, items[0]["prompt_prospect_id"])
        assert stored.voicecall_call_id == "call-123"


def test_prompt_default_limit_is_five(test_db) -> None:
    app = create_app()
    client = app.test_client()

    create_response = client.post(
        "/api/prompts",
        data=json.dumps({"prompt": "Find HR leaders in SaaS"}),
        content_type="application/json",
    )

    assert create_response.status_code == 200
    assert create_response.get_json()["requested_limit"] == 5


def test_failure_paths_surface_partial_and_failed_states(test_db) -> None:
    with SessionLocal() as db:
        prompt_partial = repositories.create_prompt(db, "Find HVAC owners", 10)
        prompt_failed = repositories.create_prompt(db, "Find plumbers", 10)

        process_prompt(db, prompt_partial, build_workflow(fail_score_on="beta-owner", fail_enrich=True))
        process_prompt(db, prompt_failed, build_workflow(fail_discovery=True))

        partial = repositories.get_prompt(db, prompt_partial.id)
        failed = repositories.get_prompt(db, prompt_failed.id)
        partial_items = repositories.list_prompt_prospects(db, prompt_partial.id)

        assert partial.status == "partial"
        assert "Scoring failed" in partial.error_text or "Enrichment failed" in partial.error_text
        assert partial_items
        assert all(item.enrichment_status != "skipped" for item in partial_items)
        assert failed.status == "failed"
        assert "Discovery failed" in failed.error_text


def test_ui_smoke_routes_render_workspace(test_db) -> None:
    app = create_app()
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Prospect desk" in page
    assert "Lead ledger" in page
