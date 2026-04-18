from __future__ import annotations

from leadflow.services.normalize import (
    choose_best_phone,
    extract_phone_candidates,
    normalize_profile_url,
    normalize_prompt_brief,
    normalize_prospect_payload,
    normalize_score_payload,
)


def test_prompt_brief_normalization_applies_defaults_and_caps_limit() -> None:
    brief = normalize_prompt_brief(
        {
            "target_roles": "Owners, Founders",
            "industries": ["HVAC", "Home Services"],
            "geographies": "Dallas; Fort Worth",
            "seniority_hints": "owner",
            "exclusions": "",
            "outreach_angle": "Lead gen support",
            "result_limit": 500,
        },
        default_limit=25,
    )

    assert brief["target_roles"] == ["Owners", "Founders"]
    assert brief["industries"] == ["HVAC", "Home Services"]
    assert brief["geographies"] == ["Dallas", "Fort Worth"]
    assert brief["seniority_hints"] == ["owner"]
    assert brief["exclusions"] == []
    assert brief["outreach_angle"] == "Lead gen support"
    assert brief["result_limit"] == 100


def test_prospect_normalization_extracts_linkedin_fields() -> None:
    prospect = normalize_prospect_payload(
        {
            "linkedinUrl": "linkedin.com/in/jane-founder/",
            "fullName": "Jane Founder",
            "headline": "Helping scale HVAC ops",
            "title": "Founder",
            "companyName": "Northwind Air",
            "companyWebsite": "https://northwindair.com",
            "location": "Dallas, TX",
        },
        source_actor="actor-1",
    )

    assert prospect is not None
    assert prospect["profile_url"] == "https://linkedin.com/in/jane-founder"
    assert prospect["company_domain"] == "northwindair.com"
    assert prospect["source_actor"] == "actor-1"


def test_prospect_normalization_handles_harvestapi_shape() -> None:
    prospect = normalize_prospect_payload(
        {
            "linkedinUrl": "https://www.linkedin.com/in/example-person",
            "firstName": "Jane",
            "lastName": "Doe",
            "summary": "HR systems leader",
            "currentPositions": [
                {
                    "title": "HRIS Director",
                    "companyName": "Example Health",
                    "companyLinkedinUrl": "https://www.linkedin.com/company/example-health",
                }
            ],
            "location": {"linkedinText": "Chicago, Illinois, United States"},
        },
        source_actor="harvestapi/linkedin-profile-search",
    )

    assert prospect is not None
    assert prospect["full_name"] == "Jane Doe"
    assert prospect["job_title"] == "HRIS Director"
    assert prospect["company_name"] == "Example Health"
    assert prospect["location"] == "Chicago, Illinois, United States"


def test_score_normalization_derives_band_when_decision_missing() -> None:
    score = normalize_score_payload({"confidence_score": "58", "score_reason": "Close fit."})
    assert score == {"ai_decision": "review", "confidence_score": 58, "score_reason": "Close fit."}


def test_phone_extraction_and_selection_normalize_to_e164() -> None:
    payload = {"phones": ["(214) 909-8059", "+1 214 555 0000"], "notes": "desk 972-555-1111"}
    phones = extract_phone_candidates(payload)

    assert "+12149098059" in phones
    assert choose_best_phone(phones) == "+12149098059"
    assert normalize_profile_url("www.linkedin.com/in/test-user") == "https://www.linkedin.com/in/test-user"
