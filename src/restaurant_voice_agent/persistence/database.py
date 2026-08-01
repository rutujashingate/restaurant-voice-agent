"""Engine and session helpers for the persistence layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from restaurant_voice_agent.config.settings import Settings

from .errors import DatabaseConfigurationError

if TYPE_CHECKING:
    pass

SessionFactory = sessionmaker[Session]


def get_database_url(settings: Settings | None = None) -> str:
    """Return the configured database URL or raise a clear error."""

    resolved_settings = settings or Settings()
    if not resolved_settings.database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL must be set before creating a database engine"
        )
    return resolved_settings.database_url


def create_engine_from_url(database_url: str, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine with sane defaults for PostgreSQL."""

    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


def create_engine_from_settings(settings: Settings | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine from application settings."""

    return create_engine_from_url(get_database_url(settings), echo=echo)


def create_session_factory(engine: Engine) -> SessionFactory:
    """Create a session factory bound to the given engine."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
