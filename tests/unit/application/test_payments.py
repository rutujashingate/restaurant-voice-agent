"""Tests for payment checkout and webhook handling."""

from __future__ import annotations

from typing import Any, Mapping

from restaurant_voice_agent.application.cart import CartContext, CartService
from restaurant_voice_agent.application.orders import OrderService
from restaurant_voice_agent.application.payments import PaymentService
from restaurant_voice_agent.domain.identifiers import ModifierId
from restaurant_voice_agent.domain.menu import ModifierSelectionRequest
from restaurant_voice_agent.domain.money import Money

from .helpers import CUSTOMER_PHONE, seed_restaurant_catalog


class RecordingCheckoutGateway:
    """Capture checkout link requests during a test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Money, str | None, Mapping[str, Any]]] = []

    def create_checkout_link(
        self,
        *,
        order_id: str,
        amount: Money,
        customer_phone: str | None,
        metadata: Mapping[str, Any],
    ) -> str:
        self.calls.append((order_id, amount, customer_phone, dict(metadata)))
        return f"https://pay.local/{order_id}"


class RecordingSmsGateway:
    """Capture SMS notifications during a test."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send_sms(self, to_number: str, body: str) -> str:
        self.messages.append((to_number, body))
        return "sms_1"


class StaticWebhookVerifier:
    """Trust only a single signature value."""

    def verify(self, *, payload: bytes, signature: str) -> bool:
        del payload
        return signature == "valid-signature"


def _seed_order(uow_factory, session):
    restaurant_id, burger, _ = seed_restaurant_catalog(session)
    cart_service = CartService(uow_factory)
    order_service = OrderService(uow_factory, cart_service=cart_service)
    cart_id = "cart_payment"

    cart_service.create_cart(CartContext(cart_id=cart_id, restaurant_id=restaurant_id))
    cart_service.add_item(
        cart_id,
        restaurant_id,
        burger.id.value,
        quantity=1,
        modifier_selections=(
            ModifierSelectionRequest(
                group_id=burger.modifier_groups[0].id,
                modifier_id=ModifierId("cheese"),
            ),
        ),
    )

    confirmed = order_service.confirm_cart(cart_id=cart_id, restaurant_id=restaurant_id)
    return confirmed.summary.order_id


def test_payment_service_creates_checkout_session_and_records_attempts(
    uow_factory, session
) -> None:
    order_id = _seed_order(uow_factory, session)
    checkout_gateway = RecordingCheckoutGateway()
    sms_gateway = RecordingSmsGateway()
    payment_service = PaymentService(
        uow_factory,
        checkout_gateway=checkout_gateway,
        sms_gateway=sms_gateway,
    )

    session_result = payment_service.create_checkout_session(
        order_id=order_id,
        customer_phone=CUSTOMER_PHONE,
    )

    assert session_result.checkout_url == f"https://pay.local/{order_id}"
    assert session_result.provider_name == "stripe"
    assert sms_gateway.messages[0][0] == CUSTOMER_PHONE
    assert "Copper Spoon Kitchen order #" in sms_gateway.messages[0][1]
    assert checkout_gateway.calls[0][0] == order_id

    with uow_factory() as uow:
        payment = uow.payments.get(session_result.payment_id)
        assert payment is not None
        assert payment.status == "PENDING"
        assert len(uow.payment_attempts.list_for_payment(payment.id)) == 1
        assert len(uow.outbox.list_unprocessed()) == 1


def test_payment_service_handles_webhooks_and_ignores_duplicates(uow_factory, session) -> None:
    order_id = _seed_order(uow_factory, session)
    payment_service = PaymentService(
        uow_factory,
        checkout_gateway=RecordingCheckoutGateway(),
        webhook_verifier=StaticWebhookVerifier(),
    )
    checkout_session = payment_service.create_checkout_session(order_id=order_id)

    payload = {
        "event_id": "evt_123",
        "payment_id": checkout_session.payment_id,
        "order_id": checkout_session.order_id,
        "provider_reference": "pi_123",
        "status": "succeeded",
        "type": "payment_intent.succeeded",
    }

    first = payment_service.handle_webhook(
        payload=payload,
        signature="valid-signature",
    )
    duplicate = payment_service.handle_webhook(
        payload=payload,
        signature="valid-signature",
    )

    assert first.duplicate is False
    assert first.status == "PAID"
    assert duplicate.duplicate is True
    assert duplicate.status == "PAID"

    with uow_factory() as uow:
        payment = uow.payments.get(checkout_session.payment_id)
        order = uow.orders.get(order_id)
        assert payment is not None
        assert order is not None
        assert payment.status == "PAID"
        assert order.status == "CONFIRMED"
        assert len(uow.payment_events.list_for_payment(payment.id)) == 1
