"""Tests for database engine and session helpers."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from restaurant_voice_agent.config.settings import Settings
from restaurant_voice_agent.persistence.database import (
    DatabaseConfigurationError,
    create_engine_from_settings,
    create_engine_from_url,
    create_session_factory,
)


def test_create_engine_from_settings_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        create_engine_from_settings(Settings())


def test_create_session_factory_binds_to_the_given_engine(sqlite_engine) -> None:
    engine = create_engine_from_url("sqlite+pysqlite://")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = session.execute(text("select 1")).scalar_one()

    assert result == 1
    assert engine.url.drivername == "sqlite+pysqlite"
