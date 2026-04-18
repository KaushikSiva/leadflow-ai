from __future__ import annotations

from pathlib import Path

import pytest

from leadflow.api import app as api_app
from leadflow.config import get_settings
from leadflow.db.base import Base
from leadflow.db.session import SessionLocal, configure_session


@pytest.fixture()
def test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "leadflow-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("APIFY_API_TOKEN", "test-apify-token")
    monkeypatch.setenv("APIFY_PROFILE_ACTOR_ID", "profile-actor")
    monkeypatch.setenv("APIFY_PHONE_ENRICH_ACTOR_ID", "phone-actor")
    monkeypatch.setenv("VOICECALL_API_BASE_URL", "http://voicecall")
    monkeypatch.setenv("VOICECALL_API_TOKEN", "voicecall-token")
    get_settings.cache_clear()
    engine = configure_session(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    api_app.run_migrations = lambda: None
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()
