from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from leadflow.config import get_settings

engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)


def configure_session(database_url: str | None = None) -> Engine:
    global engine
    url = database_url or get_settings().database_url
    connect_args: dict = {}
    if "supabase.com" in url or "pooler.supabase.com" in url:
        connect_args["prepare_threshold"] = None

    engine = create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args=connect_args,
    )
    SessionLocal.configure(bind=engine)
    return engine


def get_db() -> Generator[Session, None, None]:
    if SessionLocal.kw.get("bind") is None:
        configure_session()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
