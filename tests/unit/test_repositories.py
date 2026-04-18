from __future__ import annotations

from sqlalchemy import func, select

from leadflow.db.models import Prospect
from leadflow.db.session import SessionLocal
from leadflow import repositories


def test_upsert_prospect_dedupes_on_profile_url(test_db) -> None:
    with SessionLocal() as db:
        first = repositories.upsert_prospect(
            db,
            {
                "profile_url": "https://linkedin.com/in/test-one",
                "full_name": "Test One",
                "headline": "Original",
                "job_title": "Founder",
                "company_name": "Alpha",
                "company_domain": "alpha.com",
                "location": "Dallas",
                "source_actor": "actor-a",
                "source_payload_json": {"a": 1},
            },
        )
        second = repositories.upsert_prospect(
            db,
            {
                "profile_url": "https://linkedin.com/in/test-one",
                "full_name": "Test One",
                "headline": "Updated",
                "job_title": "Founder",
                "company_name": "Alpha",
                "company_domain": "alpha.com",
                "location": "Dallas",
                "source_actor": "actor-b",
                "source_payload_json": {"b": 2},
            },
        )
        count = db.scalar(select(func.count()).select_from(Prospect).where(Prospect.profile_url == "https://linkedin.com/in/test-one"))

    assert first.id == second.id
    assert second.headline == "Updated"
    assert count == 1
