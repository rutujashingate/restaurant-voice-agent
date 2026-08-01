"""PostgreSQL-backed integration tests."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from restaurant_voice_agent.domain.identifiers import (
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    RestaurantId,
)
from restaurant_voice_agent.domain.menu import MenuItem, Modifier, ModifierGroup
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.models import (
    Base,
    CallSessionRecord,
    CartLineRecord,
    CartRecord,
    CustomerRecord,
    IdempotencyKeyRecord,
    MenuItemRecord,
    ModifierGroupRecord,
    ModifierRecord,
    OrderLineRecord,
    OrderRecord,
    OutboxEventRecord,
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentRecord,
    RestaurantRecord,
)
from restaurant_voice_agent.persistence.repositories import (
    MenuRepository,
    RestaurantRepository,
)
from restaurant_voice_agent.persistence.seed import seed_demo_data


def _build_burger() -> MenuItem:
    toppings = ModifierGroup(
        id=ModifierGroupId("burger_toppings"),
        name="Burger toppings",
        modifiers=(
            Modifier(id=ModifierId("cheese"), name="Add cheese", price_delta=Money("1.00")),
            Modifier(id=ModifierId("onion"), name="No onion", price_delta=Money("0.00")),
        ),
        min_selected=0,
        max_selected=1,
    )
    return MenuItem(
        id=MenuItemId("classic_burger"),
        name="Classic Burger",
        base_price=Money("10.00"),
        modifier_groups=(toppings,),
    )


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture()
def postgres_session():
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.skip("Set DATABASE_URL to a PostgreSQL database to run integration tests")

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        yield session
        session.rollback()

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.integration
def test_postgresql_menu_repository_round_trip(postgres_session) -> None:
    restaurant_repo = RestaurantRepository(postgres_session)
    menu_repo = MenuRepository(postgres_session)
    restaurant_id = RestaurantId("copper_spoon_kitchen")

    restaurant_repo.upsert(
        RestaurantRecord(
            id=restaurant_id.value,
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
        )
    )

    burger = _build_burger()
    saved = menu_repo.save_menu_item(restaurant_id, burger)

    assert saved == burger
    assert menu_repo.get_menu_item(burger.id.value) == burger


@pytest.mark.integration
def test_postgresql_seed_is_repeatable(postgres_session) -> None:
    seed_demo_data(postgres_session)
    postgres_session.commit()

    first_counts = {
        "restaurants": _count(postgres_session, RestaurantRecord),
        "menu_items": _count(postgres_session, MenuItemRecord),
        "modifier_groups": _count(postgres_session, ModifierGroupRecord),
        "modifiers": _count(postgres_session, ModifierRecord),
        "customers": _count(postgres_session, CustomerRecord),
        "call_sessions": _count(postgres_session, CallSessionRecord),
        "carts": _count(postgres_session, CartRecord),
        "cart_lines": _count(postgres_session, CartLineRecord),
        "orders": _count(postgres_session, OrderRecord),
        "order_lines": _count(postgres_session, OrderLineRecord),
        "payments": _count(postgres_session, PaymentRecord),
        "payment_attempts": _count(postgres_session, PaymentAttemptRecord),
        "payment_events": _count(postgres_session, PaymentEventRecord),
        "idempotency_keys": _count(postgres_session, IdempotencyKeyRecord),
        "outbox_events": _count(postgres_session, OutboxEventRecord),
    }

    seed_demo_data(postgres_session)
    postgres_session.commit()

    second_counts = {
        "restaurants": _count(postgres_session, RestaurantRecord),
        "menu_items": _count(postgres_session, MenuItemRecord),
        "modifier_groups": _count(postgres_session, ModifierGroupRecord),
        "modifiers": _count(postgres_session, ModifierRecord),
        "customers": _count(postgres_session, CustomerRecord),
        "call_sessions": _count(postgres_session, CallSessionRecord),
        "carts": _count(postgres_session, CartRecord),
        "cart_lines": _count(postgres_session, CartLineRecord),
        "orders": _count(postgres_session, OrderRecord),
        "order_lines": _count(postgres_session, OrderLineRecord),
        "payments": _count(postgres_session, PaymentRecord),
        "payment_attempts": _count(postgres_session, PaymentAttemptRecord),
        "payment_events": _count(postgres_session, PaymentEventRecord),
        "idempotency_keys": _count(postgres_session, IdempotencyKeyRecord),
        "outbox_events": _count(postgres_session, OutboxEventRecord),
    }

    assert first_counts == second_counts
    assert first_counts["restaurants"] == 1
    assert first_counts["menu_items"] == 3
    assert first_counts["payment_attempts"] == 1
    assert first_counts["payment_events"] == 1
