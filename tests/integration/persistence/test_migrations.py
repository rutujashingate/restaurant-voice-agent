"""Integration tests for Alembic migrations against PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from restaurant_voice_agent.persistence.models import Base


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.skip("Set DATABASE_URL to a PostgreSQL database to run integration tests")
    return database_url


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.integration
def test_alembic_upgrade_and_downgrade_round_trip() -> None:
    database_url = _database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    config = _alembic_config(database_url)

    try:
        Base.metadata.drop_all(engine)

        command.upgrade(config, "head")
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert {"restaurants", "orders", "payments", "payment_attempts", "payment_events"}.issubset(
            table_names
        )

        command.downgrade(config, "base")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()
