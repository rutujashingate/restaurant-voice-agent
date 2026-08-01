"""Tests for repeatable demo seed data."""

from __future__ import annotations

from sqlalchemy import func, select

from restaurant_voice_agent.persistence.models import (
    CallSessionRecord,
    CartLineRecord,
    CartRecord,
    ComplaintRecord,
    CustomerRecord,
    HandoffRecord,
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
from restaurant_voice_agent.persistence.seed import seed_demo_data


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_demo_data_is_repeatable(session) -> None:
    seed_demo_data(session)
    session.commit()

    first_counts = {
        "restaurants": _count(session, RestaurantRecord),
        "menu_items": _count(session, MenuItemRecord),
        "modifier_groups": _count(session, ModifierGroupRecord),
        "modifiers": _count(session, ModifierRecord),
        "customers": _count(session, CustomerRecord),
        "call_sessions": _count(session, CallSessionRecord),
        "carts": _count(session, CartRecord),
        "cart_lines": _count(session, CartLineRecord),
        "orders": _count(session, OrderRecord),
        "order_lines": _count(session, OrderLineRecord),
        "payments": _count(session, PaymentRecord),
        "payment_attempts": _count(session, PaymentAttemptRecord),
        "payment_events": _count(session, PaymentEventRecord),
        "idempotency_keys": _count(session, IdempotencyKeyRecord),
        "outbox_events": _count(session, OutboxEventRecord),
        "complaints": _count(session, ComplaintRecord),
        "handoffs": _count(session, HandoffRecord),
    }

    seed_demo_data(session)
    session.commit()

    second_counts = {
        "restaurants": _count(session, RestaurantRecord),
        "menu_items": _count(session, MenuItemRecord),
        "modifier_groups": _count(session, ModifierGroupRecord),
        "modifiers": _count(session, ModifierRecord),
        "customers": _count(session, CustomerRecord),
        "call_sessions": _count(session, CallSessionRecord),
        "carts": _count(session, CartRecord),
        "cart_lines": _count(session, CartLineRecord),
        "orders": _count(session, OrderRecord),
        "order_lines": _count(session, OrderLineRecord),
        "payments": _count(session, PaymentRecord),
        "payment_attempts": _count(session, PaymentAttemptRecord),
        "payment_events": _count(session, PaymentEventRecord),
        "idempotency_keys": _count(session, IdempotencyKeyRecord),
        "outbox_events": _count(session, OutboxEventRecord),
        "complaints": _count(session, ComplaintRecord),
        "handoffs": _count(session, HandoffRecord),
    }

    assert first_counts == second_counts
    assert first_counts["restaurants"] == 1
    assert first_counts["menu_items"] == 3
    assert first_counts["cart_lines"] == 2
    assert first_counts["order_lines"] == 2
    assert first_counts["payment_attempts"] == 1
    assert first_counts["payment_events"] == 1
