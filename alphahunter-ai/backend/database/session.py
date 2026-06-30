"""Database session factory.

Degrades gracefully: ``get_engine`` returns None when no DATABASE_URL is set,
and callers should treat persistence as best-effort.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database.models import Base

_engine: Engine | None = None
_SessionLocal = None


def get_engine() -> Engine | None:
    global _engine, _SessionLocal
    if settings.database_url is None:
        return None
    if _engine is None:
        _engine = create_engine(settings.database_url, future=True)
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session():
    if get_engine() is None:
        return None
    return _SessionLocal()
