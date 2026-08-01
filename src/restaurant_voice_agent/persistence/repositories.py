"""Repository helpers that keep SQLAlchemy details behind a small API."""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from restaurant_voice_agent.domain.cart import (
    CartLineDraftSnapshot,
    SubmittedOrderLineSnapshot,
)
from restaurant_voice_agent.domain.identifiers import RestaurantId
from restaurant_voice_agent.domain.menu import MenuItem

from .errors import IdempotencyConflictError
from .mappers import (
    cart_line_from_record,
    cart_line_to_record,
    menu_item_from_record,
    menu_item_to_record,
    order_line_from_record,
    order_line_to_record,
)
from .models import (
    CallSessionRecord,
    CartLineRecord,
    CartRecord,
    ComplaintRecord,
    CustomerRecord,
    HandoffRecord,
    IdempotencyKeyRecord,
    MenuItemRecord,
    OrderLineRecord,
    OrderRecord,
    OutboxEventRecord,
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentRecord,
    RestaurantRecord,
)

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Small CRUD wrapper around a SQLAlchemy session."""

    model_type: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    def upsert(self, entity: ModelT) -> ModelT:
        merged = self.session.merge(entity)
        self.session.flush()
        return merged

    def get(self, identifier: Any) -> ModelT | None:
        return self.session.get(self.model_type, identifier)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model_type)).all())

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)


class RestaurantRepository(Repository[RestaurantRecord]):
    """Repository for restaurant records."""

    model_type = RestaurantRecord


class MenuRepository(Repository[MenuItemRecord]):
    """Repository for restaurant menu items and nested modifier graphs."""

    model_type = MenuItemRecord

    def save_menu_item(self, restaurant_id: RestaurantId, menu_item: MenuItem) -> MenuItem:
        """Insert or update a menu item and return the domain object."""

        record = menu_item_to_record(restaurant_id, menu_item)
        merged = self.session.merge(record)
        self.session.flush()
        refreshed = self.session.get(MenuItemRecord, merged.id)
        assert refreshed is not None
        return menu_item_from_record(refreshed)

    def get_menu_item(self, menu_item_id: str) -> MenuItem | None:
        record = self.session.get(MenuItemRecord, menu_item_id)
        if record is None:
            return None
        return menu_item_from_record(record)

    def list_menu_items(self, restaurant_id: str) -> list[MenuItem]:
        records = self.session.scalars(
            select(MenuItemRecord).where(MenuItemRecord.restaurant_id == restaurant_id)
        ).all()
        return [menu_item_from_record(record) for record in records]


class CustomerRepository(Repository[CustomerRecord]):
    """Repository for customers."""

    model_type = CustomerRecord

    def find_by_phone_number(self, restaurant_id: str, phone_number: str) -> CustomerRecord | None:
        return self.session.scalar(
            select(CustomerRecord).where(
                CustomerRecord.restaurant_id == restaurant_id,
                CustomerRecord.phone_number == phone_number,
            )
        )


class CallSessionRepository(Repository[CallSessionRecord]):
    """Repository for call sessions."""

    model_type = CallSessionRecord

    def find_by_provider_call_id(self, provider_call_id: str) -> CallSessionRecord | None:
        return self.session.scalar(
            select(CallSessionRecord).where(CallSessionRecord.provider_call_id == provider_call_id)
        )


class CartRepository(Repository[CartRecord]):
    """Repository for draft carts and their temporary line snapshots."""

    model_type = CartRecord

    def save_line(self, cart_id: str, line: CartLineDraftSnapshot) -> CartLineDraftSnapshot:
        record = cart_line_to_record(cart_id, line)
        merged = self.session.merge(record)
        self.session.flush()
        refreshed = self.session.get(CartLineRecord, merged.id)
        assert refreshed is not None
        return cart_line_from_record(refreshed)

    def list_lines(self, cart_id: str) -> list[CartLineDraftSnapshot]:
        records = self.session.scalars(
            select(CartLineRecord).where(CartLineRecord.cart_id == cart_id)
        ).all()
        return [cart_line_from_record(record) for record in records]

    def delete_lines(self, cart_id: str) -> None:
        self.session.execute(delete(CartLineRecord).where(CartLineRecord.cart_id == cart_id))

    def find_by_customer_id(self, customer_id: str) -> CartRecord | None:
        return self.session.scalar(select(CartRecord).where(CartRecord.customer_id == customer_id))


class OrderRepository(Repository[OrderRecord]):
    """Repository for submitted orders and their permanent snapshots."""

    model_type = OrderRecord

    def save_line(
        self, order_id: str, line: SubmittedOrderLineSnapshot
    ) -> SubmittedOrderLineSnapshot:
        record = order_line_to_record(order_id, line)
        merged = self.session.merge(record)
        self.session.flush()
        refreshed = self.session.get(OrderLineRecord, merged.id)
        assert refreshed is not None
        return order_line_from_record(refreshed)

    def list_lines(self, order_id: str) -> list[SubmittedOrderLineSnapshot]:
        records = self.session.scalars(
            select(OrderLineRecord).where(OrderLineRecord.order_id == order_id)
        ).all()
        return [order_line_from_record(record) for record in records]

    def delete_lines(self, order_id: str) -> None:
        self.session.execute(delete(OrderLineRecord).where(OrderLineRecord.order_id == order_id))

    def find_by_cart_id(self, cart_id: str) -> OrderRecord | None:
        return self.session.scalar(select(OrderRecord).where(OrderRecord.cart_id == cart_id))

    def find_by_display_number(self, display_number: int) -> OrderRecord | None:
        return self.session.scalar(
            select(OrderRecord).where(OrderRecord.display_number == display_number)
        )


class PaymentRepository(Repository[PaymentRecord]):
    """Repository for payment state."""

    model_type = PaymentRecord

    def find_by_order_id(self, order_id: str) -> PaymentRecord | None:
        return self.session.scalar(select(PaymentRecord).where(PaymentRecord.order_id == order_id))


class PaymentAttemptRepository(Repository[PaymentAttemptRecord]):
    """Repository for individual payment attempts."""

    model_type = PaymentAttemptRecord

    def record_attempt(self, attempt: PaymentAttemptRecord) -> PaymentAttemptRecord:
        existing = self.session.get(PaymentAttemptRecord, attempt.id)
        if existing is None:
            existing = self.session.scalar(
                select(PaymentAttemptRecord).where(
                    PaymentAttemptRecord.payment_id == attempt.payment_id,
                    PaymentAttemptRecord.attempt_number == attempt.attempt_number,
                )
            )
        if existing is not None:
            return existing

        merged = self.session.merge(attempt)
        self.session.flush()
        return merged

    def list_for_payment(self, payment_id: str) -> list[PaymentAttemptRecord]:
        return list(
            self.session.scalars(
                select(PaymentAttemptRecord).where(PaymentAttemptRecord.payment_id == payment_id)
            ).all()
        )


class PaymentEventRepository(Repository[PaymentEventRecord]):
    """Repository for provider payment events."""

    model_type = PaymentEventRecord

    def record_event(self, event: PaymentEventRecord) -> PaymentEventRecord:
        existing = self.session.get(PaymentEventRecord, event.id)
        if existing is None:
            existing = self.session.scalar(
                select(PaymentEventRecord).where(
                    PaymentEventRecord.provider_event_id == event.provider_event_id
                )
            )
        if existing is not None:
            return existing
        self.session.add(event)
        self.session.flush()
        return event

    def find_by_provider_event_id(self, provider_event_id: str) -> PaymentEventRecord | None:
        return self.session.scalar(
            select(PaymentEventRecord).where(
                PaymentEventRecord.provider_event_id == provider_event_id
            )
        )

    def list_for_payment(self, payment_id: str) -> list[PaymentEventRecord]:
        return list(
            self.session.scalars(
                select(PaymentEventRecord).where(PaymentEventRecord.payment_id == payment_id)
            ).all()
        )


class ComplaintRepository(Repository[ComplaintRecord]):
    """Repository for complaints."""

    model_type = ComplaintRecord

    def find_by_display_number(self, display_number: int) -> ComplaintRecord | None:
        return self.session.scalar(
            select(ComplaintRecord).where(ComplaintRecord.display_number == display_number)
        )


class HandoffRepository(Repository[HandoffRecord]):
    """Repository for human handoffs."""

    model_type = HandoffRecord

    def find_by_order_id(self, order_id: str) -> HandoffRecord | None:
        return self.session.scalar(select(HandoffRecord).where(HandoffRecord.order_id == order_id))


class IdempotencyRepository(Repository[IdempotencyKeyRecord]):
    """Repository for idempotency guard records."""

    model_type = IdempotencyKeyRecord

    def get_for_scope(self, scope: str, key: str) -> IdempotencyKeyRecord | None:
        record = self.session.get(IdempotencyKeyRecord, key)
        if record is None or record.scope != scope:
            return None
        return record

    def record_response(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        response_status: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> IdempotencyKeyRecord:
        existing = self.get_for_scope(scope, key)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "The same idempotency key cannot be reused for a different request"
                )
            existing.response_status = response_status
            existing.response_body = response_body
            return existing

        record = IdempotencyKeyRecord(
            key=key,
            scope=scope,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
        )
        self.session.add(record)
        self.session.flush()
        return record


class OutboxRepository(Repository[OutboxEventRecord]):
    """Repository for transactional outbox events."""

    model_type = OutboxEventRecord

    def enqueue(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> OutboxEventRecord:
        record = OutboxEventRecord(
            id=uuid4().hex,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
        self.session.add(record)
        return record

    def list_unprocessed(self, limit: int = 100) -> list[OutboxEventRecord]:
        return list(
            self.session.scalars(
                select(OutboxEventRecord)
                .where(OutboxEventRecord.processed_at.is_(None))
                .order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.id)
                .limit(limit)
            ).all()
        )

    def mark_processed(self, event_id: str) -> None:
        record = self.session.get(OutboxEventRecord, event_id)
        if record is not None:
            record.processed_at = record.processed_at or record.occurred_at
            record.last_error = None

    def mark_failed(self, event_id: str, error: str) -> None:
        record = self.session.get(OutboxEventRecord, event_id)
        if record is not None:
            record.attempts += 1
            record.last_error = error


__all__ = [
    "CallSessionRepository",
    "CartRepository",
    "ComplaintRepository",
    "CustomerRepository",
    "HandoffRepository",
    "IdempotencyRepository",
    "MenuRepository",
    "OrderRepository",
    "OutboxRepository",
    "PaymentAttemptRepository",
    "PaymentEventRepository",
    "PaymentRepository",
    "Repository",
    "RestaurantRepository",
]
