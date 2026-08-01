"""Payment checkout, retry, and webhook handling services."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from restaurant_voice_agent.application.errors import (
    CheckoutNotReadyError,
    NotFoundError,
    PaymentVerificationError,
)
from restaurant_voice_agent.application.models import CheckoutSession, PaymentWebhookResult
from restaurant_voice_agent.application.ports import (
    CheckoutGateway,
    SmsGateway,
    UnitOfWork,
    WebhookVerifier,
)
from restaurant_voice_agent.domain.enums import OrderStatus, PaymentStatus
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.models import (
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentRecord,
)


def _payload_text(payload: bytes | str | Mapping[str, Any]) -> str:
    if isinstance(payload, bytes):
        return payload.decode("utf-8")
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, sort_keys=True)


def _payload_mapping(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    return json.loads(_payload_text(payload))


def _normalize_payment_status(status: str) -> str:
    normalized = status.upper()
    if normalized in {"PAID", "SUCCEEDED", "COMPLETED"}:
        return PaymentStatus.PAID.value
    if normalized in {"FAILED", "DECLINED"}:
        return PaymentStatus.FAILED.value
    if normalized in {"EXPIRED", "EXPIRED_LINK"}:
        return PaymentStatus.EXPIRED.value
    if normalized in {"CANCELLED", "CANCELED"}:
        return PaymentStatus.CANCELLED.value
    if normalized == "REFUNDED":
        return PaymentStatus.REFUNDED.value
    if normalized == "PENDING":
        return PaymentStatus.PENDING.value
    if normalized == "NOT_STARTED":
        return PaymentStatus.NOT_STARTED.value
    return normalized


class DeterministicCheckoutGateway:
    """Fallback checkout-link builder used when no external gateway is configured."""

    provider_name = "deterministic"

    def create_checkout_link(
        self,
        *,
        order_id: str,
        amount: Money,
        customer_phone: str | None,
        metadata: Mapping[str, Any],
    ) -> str:
        del customer_phone, metadata
        return f"https://checkout.local/{order_id}?amount={amount.amount}"


class PaymentService:
    """Create payment checkout sessions and process provider webhooks."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        checkout_gateway: CheckoutGateway | None = None,
        sms_gateway: SmsGateway | None = None,
        webhook_verifier: WebhookVerifier | None = None,
        provider_name: str = "stripe",
    ) -> None:
        self.uow_factory = uow_factory
        self.checkout_gateway = checkout_gateway or DeterministicCheckoutGateway()
        self.sms_gateway = sms_gateway
        self.webhook_verifier = webhook_verifier
        self.provider_name = provider_name

    def create_checkout_session(
        self,
        *,
        order_id: str,
        customer_phone: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        send_sms: bool = True,
    ) -> CheckoutSession:
        metadata = dict(metadata or {})
        with self.uow_factory() as uow:
            order = uow.orders.get(order_id)
            if order is None:
                raise NotFoundError(f"Order {order_id!r} was not found")
            if order.status == OrderStatus.CONFIRMED.value:
                raise CheckoutNotReadyError(
                    "Confirmed orders cannot be sent through checkout again"
                )

            payment = uow.payments.find_by_order_id(order_id)
            if payment is None:
                payment = uow.payments.upsert(
                    PaymentRecord(
                        id=f"payment_{order_id}",
                        order_id=order_id,
                        status=PaymentStatus.NOT_STARTED.value,
                        amount_amount=order.subtotal_amount,
                        amount_currency=order.subtotal_currency,
                        raw_payload={},
                    )
                )

            attempt_number = len(uow.payment_attempts.list_for_payment(payment.id)) + 1
            provider_reference = f"{self.provider_name}_{payment.id}_attempt_{attempt_number}"
            attempt = uow.payment_attempts.record_attempt(
                PaymentAttemptRecord(
                    id=f"{payment.id}_attempt_{attempt_number}",
                    payment_id=payment.id,
                    attempt_number=attempt_number,
                    provider=self.provider_name,
                    provider_reference=provider_reference,
                    status=PaymentStatus.PENDING.value,
                    request_payload={
                        "order_id": order.id,
                        "display_number": order.display_number,
                        "amount": str(order.subtotal_amount),
                        "currency": order.subtotal_currency,
                    },
                    response_payload={},
                )
            )

            checkout_url = self.checkout_gateway.create_checkout_link(
                order_id=order.id,
                amount=Money(order.subtotal_amount, currency=order.subtotal_currency),
                customer_phone=customer_phone,
                metadata={
                    "order_id": order.id,
                    "payment_id": payment.id,
                    **metadata,
                },
            )

            sms_body = (
                f"Copper Spoon Kitchen order #{order.display_number}: "
                f"pay {Money(order.subtotal_amount, currency=order.subtotal_currency)} "
                f"at {checkout_url}"
            )
            if send_sms and customer_phone is not None and self.sms_gateway is not None:
                self.sms_gateway.send_sms(customer_phone, sms_body)

            payment.status = PaymentStatus.PENDING.value
            payment.provider = self.provider_name
            payment.provider_reference = provider_reference
            payment.raw_payload = {
                "checkout_url": checkout_url,
                "attempt_id": attempt.id,
                "metadata": metadata,
            }
            payment.captured_at = None
            uow.outbox.enqueue(
                aggregate_type="payment",
                aggregate_id=payment.id,
                event_type="payment.checkout_link.created",
                payload={
                    "order_id": order.id,
                    "payment_id": payment.id,
                    "checkout_url": checkout_url,
                    "attempt_number": attempt_number,
                },
            )

            return CheckoutSession(
                order_id=order.id,
                payment_id=payment.id,
                checkout_url=checkout_url,
                amount=Money(order.subtotal_amount, currency=order.subtotal_currency),
                sms_body=sms_body,
                provider_reference=provider_reference,
                provider_name=self.provider_name,
                metadata={
                    "attempt_id": attempt.id,
                    **metadata,
                },
            )

    def handle_webhook(
        self,
        *,
        payload: bytes | str | Mapping[str, Any],
        signature: str,
    ) -> PaymentWebhookResult:
        if self.webhook_verifier is None:
            raise PaymentVerificationError(
                "A webhook verifier is required to trust provider events"
            )
        raw_text = _payload_text(payload)
        if not self.webhook_verifier.verify(payload=raw_text.encode("utf-8"), signature=signature):
            raise PaymentVerificationError("Payment webhook signature could not be verified")

        event = _payload_mapping(payload)
        event_id = str(event["event_id"])
        payment_id = str(event["payment_id"])
        order_id = str(event["order_id"])
        event_type = str(event.get("type", event.get("event_type", "payment.intent.succeeded")))
        status = _normalize_payment_status(str(event.get("status", "PAID")))

        with self.uow_factory() as uow:
            payment = uow.payments.get(payment_id) or uow.payments.find_by_order_id(order_id)
            if payment is None:
                raise NotFoundError(f"Payment for order {order_id!r} was not found")

            existing_event = uow.payment_events.find_by_provider_event_id(event_id)
            if existing_event is not None:
                return PaymentWebhookResult(
                    event_id=event_id,
                    order_id=order_id,
                    payment_id=payment.id,
                    status=payment.status,
                    duplicate=True,
                    processed_at=existing_event.processed_at,
                )

            recorded_event = uow.payment_events.record_event(
                PaymentEventRecord(
                    id=event_id,
                    payment_id=payment.id,
                    provider_event_id=event_id,
                    event_type=event_type,
                    payload=event,
                    received_at=datetime.now(timezone.utc),
                )
            )

            order = uow.orders.get(payment.order_id)
            if order is None:
                raise NotFoundError(f"Order {payment.order_id!r} was not found")

            provider_reference = str(event.get("provider_reference", payment.provider_reference))
            payment.provider_reference = provider_reference
            payment.raw_payload = dict(event)
            payment.status = status

            now = datetime.now(timezone.utc)
            if payment.status == PaymentStatus.PAID.value:
                payment.captured_at = now
                order.status = OrderStatus.CONFIRMED.value
                order.confirmed_at = order.confirmed_at or now
                uow.outbox.enqueue(
                    aggregate_type="order",
                    aggregate_id=order.id,
                    event_type="order.confirmed",
                    payload={
                        "order_id": order.id,
                        "payment_id": payment.id,
                        "display_number": order.display_number,
                    },
                )
            elif payment.status == PaymentStatus.EXPIRED.value:
                payment.captured_at = None
                order.status = OrderStatus.PAYMENT_EXPIRED.value
            elif payment.status == PaymentStatus.FAILED.value:
                payment.captured_at = None
                order.status = OrderStatus.AWAITING_PAYMENT.value
            else:
                payment.captured_at = None

            recorded_event.processed_at = now
            return PaymentWebhookResult(
                event_id=event_id,
                order_id=order.id,
                payment_id=payment.id,
                status=payment.status,
                duplicate=False,
                processed_at=recorded_event.processed_at,
            )
