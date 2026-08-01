"""SQLAlchemy ORM models for the persistence layer."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column, relationship

from restaurant_voice_agent.domain.enums import ComplaintCategory, OrderStatus, PaymentStatus


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base used by Alembic and the ORM."""


class TimestampMixin:
    """Shared created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class RestaurantRecord(TimestampMixin, Base):
    """Restaurant metadata and ownership boundary."""

    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32))

    menu_items: Mapped[list["MenuItemRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    customers: Mapped[list["CustomerRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    call_sessions: Mapped[list["CallSessionRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    carts: Mapped[list["CartRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    orders: Mapped[list["OrderRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    complaints: Mapped[list["ComplaintRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    handoffs: Mapped[list["HandoffRecord"]] = relationship(
        back_populates="restaurant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MenuItemRecord(TimestampMixin, Base):
    """Authoritative menu item stored in the catalog."""

    __tablename__ = "menu_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    base_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    base_price_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allergens: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    restaurant: Mapped["RestaurantRecord"] = relationship(
        back_populates="menu_items", lazy="selectin"
    )
    modifier_groups: Mapped[list["ModifierGroupRecord"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ModifierGroupRecord(TimestampMixin, Base):
    """A group of mutually related modifiers for a menu item."""

    __tablename__ = "modifier_groups"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "name", name="uq_modifier_groups_menu_item_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    menu_item_id: Mapped[str] = mapped_column(ForeignKey("menu_items.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    min_selected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_selected: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    menu_item: Mapped["MenuItemRecord"] = relationship(
        back_populates="modifier_groups",
        lazy="selectin",
    )
    modifiers: Mapped[list["ModifierRecord"]] = relationship(
        back_populates="modifier_group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ModifierRecord(TimestampMixin, Base):
    """An individual selectable modifier."""

    __tablename__ = "modifiers"
    __table_args__ = (
        UniqueConstraint("modifier_group_id", "name", name="uq_modifiers_group_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    modifier_group_id: Mapped[str] = mapped_column(ForeignKey("modifier_groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price_delta_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_delta_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    modifier_group: Mapped["ModifierGroupRecord"] = relationship(
        back_populates="modifiers",
        lazy="selectin",
    )


class CustomerRecord(TimestampMixin, Base):
    """Customer record linked to a restaurant."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    restaurant: Mapped["RestaurantRecord"] = relationship(
        back_populates="customers", lazy="selectin"
    )
    call_sessions: Mapped[list["CallSessionRecord"]] = relationship(
        back_populates="customer",
        lazy="selectin",
    )
    carts: Mapped[list["CartRecord"]] = relationship(back_populates="customer", lazy="selectin")
    orders: Mapped[list["OrderRecord"]] = relationship(back_populates="customer", lazy="selectin")
    complaints: Mapped[list["ComplaintRecord"]] = relationship(
        back_populates="customer",
        lazy="selectin",
    )
    handoffs: Mapped[list["HandoffRecord"]] = relationship(
        back_populates="customer",
        lazy="selectin",
    )


class CallSessionRecord(TimestampMixin, Base):
    """A call session or conversation context."""

    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))
    provider_call_id: Mapped[Optional[str]] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32), default="voice", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    restaurant: Mapped["RestaurantRecord"] = relationship(
        back_populates="call_sessions",
        lazy="selectin",
    )
    customer: Mapped[Optional["CustomerRecord"]] = relationship(
        back_populates="call_sessions",
        lazy="selectin",
    )
    carts: Mapped[list["CartRecord"]] = relationship(back_populates="call_session", lazy="selectin")
    orders: Mapped[list["OrderRecord"]] = relationship(
        back_populates="call_session", lazy="selectin"
    )


class CartRecord(TimestampMixin, Base):
    """Draft cart persisted while the customer is still making decisions."""

    __tablename__ = "carts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))
    call_session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("call_sessions.id"))
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="voice", nullable=False)

    restaurant: Mapped["RestaurantRecord"] = relationship(back_populates="carts", lazy="selectin")
    customer: Mapped[Optional["CustomerRecord"]] = relationship(
        back_populates="carts", lazy="selectin"
    )
    call_session: Mapped[Optional["CallSessionRecord"]] = relationship(
        back_populates="carts",
        lazy="selectin",
    )
    submitted_order: Mapped[Optional["OrderRecord"]] = relationship(
        back_populates="cart",
        uselist=False,
        lazy="selectin",
    )
    lines: Mapped[list["CartLineRecord"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CartLineRecord(TimestampMixin, Base):
    """Temporary cart-line snapshot."""

    __tablename__ = "cart_lines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), nullable=False)
    menu_item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    menu_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    cart: Mapped["CartRecord"] = relationship(back_populates="lines", lazy="selectin")


class OrderRecord(TimestampMixin, Base):
    """Permanent submitted order snapshot."""

    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("display_number", name="uq_orders_display_number"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_number: Mapped[int] = mapped_column(Integer, nullable=False)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))
    call_session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("call_sessions.id"))
    cart_id: Mapped[Optional[str]] = mapped_column(ForeignKey("carts.id"), unique=True)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.DRAFT.value, nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    restaurant: Mapped["RestaurantRecord"] = relationship(back_populates="orders", lazy="selectin")
    customer: Mapped[Optional["CustomerRecord"]] = relationship(
        back_populates="orders", lazy="selectin"
    )
    call_session: Mapped[Optional["CallSessionRecord"]] = relationship(
        back_populates="orders",
        lazy="selectin",
    )
    cart: Mapped[Optional["CartRecord"]] = relationship(
        back_populates="submitted_order",
        lazy="selectin",
    )
    lines: Mapped[list["OrderLineRecord"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payment: Mapped[Optional["PaymentRecord"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    complaints: Mapped[list["ComplaintRecord"]] = relationship(
        back_populates="order",
        lazy="selectin",
    )
    handoffs: Mapped[list["HandoffRecord"]] = relationship(
        back_populates="order",
        lazy="selectin",
    )


class OrderLineRecord(TimestampMixin, Base):
    """Permanent submitted-order line snapshot."""

    __tablename__ = "order_lines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    menu_item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    menu_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    order: Mapped["OrderRecord"] = relationship(back_populates="lines", lazy="selectin")


class PaymentRecord(TimestampMixin, Base):
    """Payment state stored separately from orders."""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_id", name="uq_payments_order_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=PaymentStatus.NOT_STARTED.value, nullable=False
    )
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    provider_reference: Mapped[Optional[str]] = mapped_column(String(128))
    amount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped["OrderRecord"] = relationship(back_populates="payment", lazy="selectin")
    attempts: Mapped[list["PaymentAttemptRecord"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    provider_events: Mapped[list["PaymentEventRecord"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PaymentAttemptRecord(TimestampMixin, Base):
    """A single attempt to process a payment."""

    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "attempt_number",
            name="uq_payment_attempts_payment_attempt_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    provider_reference: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    payment: Mapped["PaymentRecord"] = relationship(back_populates="attempts", lazy="selectin")
    provider_events: Mapped[list["PaymentEventRecord"]] = relationship(
        back_populates="attempt",
        lazy="selectin",
    )


class PaymentEventRecord(TimestampMixin, Base):
    """A provider event associated with a payment attempt or payment."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False)
    payment_attempt_id: Mapped[Optional[str]] = mapped_column(ForeignKey("payment_attempts.id"))
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    payment: Mapped["PaymentRecord"] = relationship(
        back_populates="provider_events",
        lazy="selectin",
    )
    attempt: Mapped[Optional["PaymentAttemptRecord"]] = relationship(
        back_populates="provider_events",
        lazy="selectin",
    )


class ComplaintRecord(TimestampMixin, Base):
    """Customer complaint or issue record."""

    __tablename__ = "complaints"
    __table_args__ = (UniqueConstraint("display_number", name="uq_complaints_display_number"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_number: Mapped[int] = mapped_column(Integer, nullable=False)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(ForeignKey("orders.id"))
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(
        String(32), default=ComplaintCategory.OTHER.value, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    resolution: Mapped[Optional[str]] = mapped_column(Text)

    restaurant: Mapped["RestaurantRecord"] = relationship(
        back_populates="complaints", lazy="selectin"
    )
    order: Mapped[Optional["OrderRecord"]] = relationship(
        back_populates="complaints",
        lazy="selectin",
    )
    customer: Mapped[Optional["CustomerRecord"]] = relationship(
        back_populates="complaints",
        lazy="selectin",
    )


class HandoffRecord(TimestampMixin, Base):
    """Human escalation or support handoff record."""

    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(ForeignKey("orders.id"))
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    restaurant: Mapped["RestaurantRecord"] = relationship(
        back_populates="handoffs", lazy="selectin"
    )
    order: Mapped[Optional["OrderRecord"]] = relationship(
        back_populates="handoffs",
        lazy="selectin",
    )
    customer: Mapped[Optional["CustomerRecord"]] = relationship(
        back_populates="handoffs",
        lazy="selectin",
    )


class IdempotencyKeyRecord(TimestampMixin, Base):
    """Idempotency guard for retry-safe operations."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_status: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class OutboxEventRecord(TimestampMixin, Base):
    """Transactional outbox event for later asynchronous publishing."""

    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)


def _next_display_number(
    connection: Connection, model: type[OrderRecord] | type[ComplaintRecord]
) -> int:
    """Return the next display number for a table within the current transaction."""

    statement = select(func.coalesce(func.max(model.display_number), 0) + 1)
    return int(connection.execute(statement).scalar_one())


@event.listens_for(OrderRecord, "before_insert")
def _assign_order_display_number(
    mapper: Mapper[OrderRecord], connection: Connection, target: OrderRecord
) -> None:
    del mapper
    if target.display_number is None:
        target.display_number = _next_display_number(connection, OrderRecord)


@event.listens_for(ComplaintRecord, "before_insert")
def _assign_complaint_display_number(
    mapper: Mapper[ComplaintRecord], connection: Connection, target: ComplaintRecord
) -> None:
    del mapper
    if target.display_number is None:
        target.display_number = _next_display_number(connection, ComplaintRecord)


__all__ = [
    "Base",
    "CallSessionRecord",
    "CartLineRecord",
    "CartRecord",
    "ComplaintRecord",
    "CustomerRecord",
    "HandoffRecord",
    "IdempotencyKeyRecord",
    "MenuItemRecord",
    "ModifierGroupRecord",
    "ModifierRecord",
    "OrderLineRecord",
    "OrderRecord",
    "OutboxEventRecord",
    "PaymentAttemptRecord",
    "PaymentEventRecord",
    "PaymentRecord",
    "RestaurantRecord",
    "TimestampMixin",
    "utcnow",
]
