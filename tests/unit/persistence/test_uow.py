"""Tests for the SQLAlchemy unit of work."""

from __future__ import annotations

import pytest

from restaurant_voice_agent.persistence.database import create_session_factory
from restaurant_voice_agent.persistence.models import RestaurantRecord
from restaurant_voice_agent.persistence.unit_of_work import SqlAlchemyUnitOfWork


def test_unit_of_work_commits_successful_work(sqlite_engine) -> None:
    uow = SqlAlchemyUnitOfWork(create_session_factory(sqlite_engine))

    with uow:
        assert uow.restaurants is not None
        uow.restaurants.upsert(
            RestaurantRecord(
                id="copper_spoon_kitchen",
                name="Copper Spoon Kitchen",
                timezone="America/Phoenix",
            )
        )

    with create_session_factory(sqlite_engine)() as session:
        record = session.get(RestaurantRecord, "copper_spoon_kitchen")

    assert record is not None
    assert record.name == "Copper Spoon Kitchen"


def test_unit_of_work_rolls_back_on_error(sqlite_engine) -> None:
    uow = SqlAlchemyUnitOfWork(create_session_factory(sqlite_engine))

    with pytest.raises(RuntimeError):
        with uow:
            assert uow.restaurants is not None
            uow.restaurants.upsert(
                RestaurantRecord(
                    id="copper_spoon_kitchen",
                    name="Copper Spoon Kitchen",
                    timezone="America/Phoenix",
                )
            )
            raise RuntimeError("boom")

    with create_session_factory(sqlite_engine)() as session:
        record = session.get(RestaurantRecord, "copper_spoon_kitchen")

    assert record is None
