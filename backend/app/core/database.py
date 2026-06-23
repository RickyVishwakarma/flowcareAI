"""SQLAlchemy engine, session factory, and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# SQLite (used for local smoke tests) needs a special connect arg.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
)


def get_db() -> Generator:
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables from ORM metadata (dev/test convenience).

    Production uses db/schema.sql + Alembic migrations instead. `create_all`
    only creates *missing tables* — it never adds columns to an existing one,
    so a local SQLite dev DB goes stale after a model change. For SQLite in
    non-production we detect that drift and rebuild (data is disposable in dev).
    """
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    if settings.database_url.startswith("sqlite") and not settings.is_production:
        _rebuild_sqlite_if_stale()

    Base.metadata.create_all(bind=engine)


def _rebuild_sqlite_if_stale() -> None:
    """Drop + recreate the dev SQLite schema if any table is missing columns."""
    import logging

    from sqlalchemy import inspect

    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        expected = {col.name for col in table.columns}
        if not expected.issubset(existing):
            logging.getLogger(__name__).warning(
                "Dev SQLite schema is stale (table '%s' missing %s) — rebuilding "
                "all tables. Local data will be reset.",
                table.name,
                sorted(expected - existing),
            )
            Base.metadata.drop_all(bind=engine)
            return
