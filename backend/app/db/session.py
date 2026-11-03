"""Engine, session factory and schema bootstrap."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # survives Postgres restarts in compose
    pool_recycle=1800,
    future=True,
)

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables if absent.

    Deliberate choice over Alembic: the schema ships with the prototype and
    there is no migration history to preserve. The models are import-ordered
    here so metadata is fully populated before create_all.
    """
    from app.db import models  # noqa: F401  (registers mappers)
    from app.db.base import Base

    Base.metadata.create_all(bind=engine)
    log.info("database schema ready")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for jobs and scripts."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
