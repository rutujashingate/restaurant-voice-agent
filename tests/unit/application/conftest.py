"""Fixtures for application-layer unit tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from restaurant_voice_agent.persistence.database import create_session_factory
from restaurant_voice_agent.persistence.models import Base
from restaurant_voice_agent.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture()
def sqlite_engine():
    """Create a fresh in-memory SQLite engine for each test."""

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session(sqlite_engine) -> Iterator[Session]:
    """Create a SQLAlchemy session bound to the test engine."""

    session_factory = sessionmaker(bind=sqlite_engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
        session.rollback()


@pytest.fixture()
def uow_factory(sqlite_engine):
    """Build a unit-of-work factory bound to the in-memory test engine."""

    session_factory = create_session_factory(sqlite_engine)

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory
