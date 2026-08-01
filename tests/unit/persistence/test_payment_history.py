"""Tests for payment attempts and provider event history."""

from __future__ import annotations

from decimal import Decimal

from restaurant_voice_agent.domain.enums import OrderStatus, PaymentStatus
from restaurant_voice_agent.persistence.models import (
    OrderRecord,
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentRecord,
    RestaurantRecord,
)
from restaurant_voice_agent.persistence.repositories import (
    OrderRepository,
    PaymentAttemptRepository,
    PaymentEventRepository,
    PaymentRepository,
    RestaurantRepository,
)


def test_payment_history_round_trips_and_deduplicates_events(session) -> None:
    restaurant_repo = RestaurantRepository(session)
    order_repo = OrderRepository(session)
    payment_repo = PaymentRepository(session)
    attempt_repo = PaymentAttemptRepository(session)
    event_repo = PaymentEventRepository(session)

    restaurant_repo.upsert(
        RestaurantRecord(
            id="copper_spoon_kitchen",
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
        )
    )

    order = order_repo.upsert(
        OrderRecord(
            id="order_demo",
            restaurant_id="copper_spoon_kitchen",
            status=OrderStatus.AWAITING_PAYMENT.value,
            subtotal_amount=Decimal("15.00"),
            subtotal_currency="USD",
        )
    )
    assert order.display_number > 0

    payment = payment_repo.upsert(
        PaymentRecord(
            id="payment_demo",
            order_id=order.id,
            status=PaymentStatus.PENDING.value,
            provider="stripe",
            amount_amount=Decimal("15.00"),
            amount_currency="USD",
            raw_payload={"source": "checkout"},
        )
    )

    first_attempt = attempt_repo.record_attempt(
        PaymentAttemptRecord(
            id="attempt_1",
            payment_id=payment.id,
            attempt_number=1,
            provider="stripe",
            provider_reference="pi_demo_attempt_1",
            status=PaymentStatus.PENDING.value,
            request_payload={"source": "checkout"},
            response_payload={"status": "pending"},
        )
    )
    second_attempt = attempt_repo.record_attempt(
        PaymentAttemptRecord(
            id="attempt_2",
            payment_id=payment.id,
            attempt_number=2,
            provider="stripe",
            provider_reference="pi_demo_attempt_2",
            status=PaymentStatus.PAID.value,
            request_payload={"source": "checkout"},
            response_payload={"status": "paid"},
        )
    )

    first_event = event_repo.record_event(
        PaymentEventRecord(
            id="event_1",
            payment_id=payment.id,
            payment_attempt_id=first_attempt.id,
            provider_event_id="evt_demo_1",
            event_type="payment_intent.succeeded",
            payload={"provider_event_id": "evt_demo_1"},
        )
    )
    duplicate_event = event_repo.record_event(
        PaymentEventRecord(
            id="event_2",
            payment_id=payment.id,
            payment_attempt_id=second_attempt.id,
            provider_event_id="evt_demo_1",
            event_type="payment_intent.succeeded",
            payload={"provider_event_id": "evt_demo_1", "duplicate": True},
        )
    )

    loaded_payment = payment_repo.get(payment.id)
    assert loaded_payment is not None
    assert [attempt.attempt_number for attempt in loaded_payment.attempts] == [1, 2]
    assert len(loaded_payment.provider_events) == 1
    assert loaded_payment.provider_events[0].provider_event_id == "evt_demo_1"
    assert first_event.id == duplicate_event.id
