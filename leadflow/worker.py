from __future__ import annotations

import logging
import time

from leadflow.config import get_settings
from leadflow.db.migrate import run_migrations
from leadflow.db.session import SessionLocal, configure_session
from leadflow import repositories
from leadflow.services.workflow import build_context, process_prompt

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
logger = logging.getLogger(__name__)


def process_once() -> bool:
    settings = get_settings()
    configure_session(settings.database_url)
    workflow = build_context(settings)
    with SessionLocal() as db:
        prompt = repositories.lease_next_prompt(db)
        if not prompt:
            return False
        logger.info("picked prompt %s", prompt.id)
        process_prompt(db, prompt, workflow)
        return True


def main() -> None:
    settings = get_settings()
    configure_session(settings.database_url)
    run_migrations()
    logger.info("worker started")
    while True:
        processed = False
        for _ in range(settings.worker_batch_size):
            processed = process_once() or processed
        if not processed:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
