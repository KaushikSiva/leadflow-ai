from __future__ import annotations

from alembic import command
from alembic.config import Config

from leadflow.config import get_settings
from leadflow.db.session import configure_session


def run_migrations() -> None:
    settings = get_settings()
    configure_session(settings.database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
