"""Order confirmation and checkout-preparation services."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from restaurant_voice_agent.application.cart import CartService
from restaurant_voice_agent.application.catalog import PriceRevalidationService
from restaurant_voice_agent.application.errors import (
    CheckoutNotReadyError,
    NotFoundError,
    PriceRevalidationError,
)
from restaurant_voice_agent.application.models import CheckoutPreview, OrderSummary
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.domain.cart import Cart
from restaurant_voice_agent.domain.enums import OrderStatus, PaymentStatus
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.models import CartRecord, OrderRecord, PaymentRecord


def _canonical_payload(parts: Iterable[object]) -> str:
    return json.dumps(list(parts), sort_keys=True, default=str, separators=(",", ":"))


def _request_hash(parts: Iterable[object]) -> str:
    payload = _canonical_payload(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfirmedCartResult:
    """A persisted order ready for payment checkout."""

    summary: OrderSummary
    preview: CheckoutPreview


class OrderService:
    """Manage checkout previews and permanent order snapshots."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        cart_service: CartService | None = None,
        price_revalidation_service: PriceRevalidationService | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.cart_service = cart_service or CartService(uow_factory)
        self.price_revalidation_service = price_revalidation_service or PriceRevalidationService(
            uow_factory
        )

    def preview_checkout(self, cart_id: str, restaurant_id: str) -> CheckoutPreview:
        cart = self.cart_service.load_domain_cart(cart_id)
        revalidation = self.price_revalidation_service.revalidate_cart(restaurant_id, cart)
        message = (
            "Cart is ready for checkout."
            if revalidation.is_clean
            else "Cart changed before checkout."
        )
        return CheckoutPreview(
            cart_id=cart_id,
            quote=revalidation.quote,
            issues=revalidation.issues,
            ready=revalidation.is_clean,
            message=message,
        )

    def confirm_cart(
        self,
        *,
        cart_id: str,
        restaurant_id: str,
        customer_id: str | None = None,
        call_session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ConfirmedCartResult:
        preview = self.preview_checkout(cart_id, restaurant_id)
        if not preview.ready:
            raise PriceRevalidationError(
                "Cart cannot be confirmed until the live prices and availability are accepted"
            )

        with self.uow_factory() as uow:
            cart_record = uow.carts.get(cart_id)
            if cart_record is None:
                raise NotFoundError(f"Cart {cart_id!r} was not found")

            cart = Cart(lines=tuple(uow.carts.list_lines(cart_id)))
            if not cart.lines:
                raise CheckoutNotReadyError("Cart must contain at least one item before checkout")

            existing_order = uow.orders.find_by_cart_id(cart_id)
            if existing_order is not None:
                return ConfirmedCartResult(
                    summary=self._build_order_summary(uow, existing_order.id),
                    preview=preview,
                )

            if cart_record.status != "OPEN":
                raise CheckoutNotReadyError("Cart has already been submitted")

            request_digest = _request_hash(
                [
                    cart_id,
                    restaurant_id,
                    customer_id,
                    call_session_id,
                    [asdict(line) for line in cart.lines],
                ]
            )
            if idempotency_key is not None:
                existing_key = uow.idempotency.get_for_scope("checkout.confirm", idempotency_key)
                if existing_key is not None:
                    if existing_key.request_hash != request_digest:
                        raise CheckoutNotReadyError(
                            "This checkout request key was already used for a different cart"
                        )
                    if existing_key.response_body and existing_key.response_body.get("order_id"):
                        order_id = existing_key.response_body["order_id"]
                        return ConfirmedCartResult(
                            summary=self._build_order_summary(uow, order_id),
                            preview=preview,
                        )

            order = uow.orders.upsert(
                OrderRecord(
                    id=f"order_{cart_id}",
                    restaurant_id=restaurant_id,
                    customer_id=customer_id,
                    call_session_id=call_session_id,
                    cart_id=cart_id,
                    status=OrderStatus.AWAITING_PAYMENT.value,
                    subtotal_amount=preview.quote.total.amount,
                    subtotal_currency=preview.quote.total.currency,
                    confirmed_at=None,
                    notes="Confirmed from a live revalidated cart.",
                )
            )
            uow.orders.delete_lines(order.id)
            for line in cart.lines:
                uow.orders.save_line(order.id, line.to_submitted_snapshot())

            uow.payments.upsert(
                PaymentRecord(
                    id=f"payment_{cart_id}",
                    order_id=order.id,
                    status=PaymentStatus.NOT_STARTED.value,
                    amount_amount=preview.quote.total.amount,
                    amount_currency=preview.quote.total.currency,
                    raw_payload={"source": "checkout_preview", "cart_id": cart_id},
                )
            )

            uow.carts.upsert(
                CartRecord(
                    id=cart_id,
                    restaurant_id=restaurant_id,
                    customer_id=customer_id,
                    call_session_id=call_session_id,
                    status="SUBMITTED",
                    source=cart_record.source,
                )
            )

            if idempotency_key is not None:
                uow.idempotency.record_response(
                    scope="checkout.confirm",
                    key=idempotency_key,
                    request_hash=request_digest,
                    response_status=200,
                    response_body={"order_id": order.id},
                )

            return ConfirmedCartResult(
                summary=self._build_order_summary(uow, order.id),
                preview=preview,
            )

    def get_order(self, order_id: str) -> OrderSummary:
        with self.uow_factory() as uow:
            record = uow.orders.get(order_id)
            if record is None:
                raise NotFoundError(f"Order {order_id!r} was not found")
            return self._build_order_summary(uow, order_id)

    def get_order_by_display_number(self, display_number: int) -> OrderSummary:
        with self.uow_factory() as uow:
            record = uow.orders.find_by_display_number(display_number)
            if record is None:
                raise NotFoundError(f"Order {display_number!r} was not found")
            return self._build_order_summary(uow, record.id)

    def _build_order_summary(self, uow: UnitOfWork, order_id: str) -> OrderSummary:
        record = uow.orders.get(order_id)
        if record is None:
            raise NotFoundError(f"Order {order_id!r} was not found")

        payment = uow.payments.find_by_order_id(order_id)
        lines = tuple(uow.orders.list_lines(order_id))
        return OrderSummary(
            order_id=record.id,
            display_number=record.display_number,
            status=record.status,
            subtotal=Money(record.subtotal_amount, currency=record.subtotal_currency),
            cart_id=record.cart_id,
            payment_status=payment.status if payment is not None else None,
            confirmed_at=record.confirmed_at,
            lines=lines,
        )
