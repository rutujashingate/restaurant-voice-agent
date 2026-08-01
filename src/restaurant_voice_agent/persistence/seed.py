"""Repeatable demo seed data for local development and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from restaurant_voice_agent.config.settings import Settings
from restaurant_voice_agent.domain.cart import Cart, CartLineDraftSnapshot
from restaurant_voice_agent.domain.enums import OrderStatus, PaymentStatus
from restaurant_voice_agent.domain.identifiers import (
    CallSessionId,
    CartLineId,
    CustomerId,
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    OrderId,
    PaymentId,
    RestaurantId,
)
from restaurant_voice_agent.domain.menu import (
    MenuItem,
    Modifier,
    ModifierGroup,
    ModifierSelectionRequest,
)
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.domain.pricing import calculate_cart_pricing

from .database import create_engine_from_settings, create_session_factory
from .errors import SeedError
from .models import (
    Base,
    CallSessionRecord,
    CartRecord,
    CustomerRecord,
    OrderRecord,
    OutboxEventRecord,
    PaymentAttemptRecord,
    PaymentEventRecord,
    PaymentRecord,
    RestaurantRecord,
    utcnow,
)
from .repositories import (
    CallSessionRepository,
    CartRepository,
    CustomerRepository,
    IdempotencyRepository,
    MenuRepository,
    OrderRepository,
    OutboxRepository,
    PaymentAttemptRepository,
    PaymentEventRepository,
    PaymentRepository,
    RestaurantRepository,
)

RESTAURANT_ID = RestaurantId("copper_spoon_kitchen")
CUSTOMER_ID = CustomerId("maya_patel")
CALL_SESSION_ID = CallSessionId("call_demo_001")
CART_ID = "cart_demo_001"
ORDER_ID = OrderId("order_demo_001")
PAYMENT_ID = PaymentId("payment_demo_001")
CHECKOUT_IDEMPOTENCY_KEY = "checkout_demo_001"
OUTBOX_EVENT_ID = "outbox_demo_001"


def _build_burger() -> MenuItem:
    toppings = ModifierGroup(
        id=ModifierGroupId("burger_toppings"),
        name="Choose your toppings",
        modifiers=(
            Modifier(
                id=ModifierId("cheese"),
                name="Add cheese",
                price_delta=Money(Decimal("1.00")),
            ),
            Modifier(
                id=ModifierId("onion"),
                name="No onion",
                price_delta=Money(Decimal("0.00")),
            ),
            Modifier(
                id=ModifierId("pickle"),
                name="No pickle",
                price_delta=Money(Decimal("0.00")),
            ),
        ),
        min_selected=0,
        max_selected=2,
    )
    return MenuItem(
        id=MenuItemId("classic_burger"),
        name="Classic Burger",
        base_price=Money(Decimal("10.00")),
        modifier_groups=(toppings,),
        allergens=("wheat", "dairy"),
    )


def _build_fries() -> MenuItem:
    seasoning = ModifierGroup(
        id=ModifierGroupId("fries_seasoning"),
        name="Seasoning",
        modifiers=(
            Modifier(
                id=ModifierId("regular"),
                name="Regular salt",
                price_delta=Money(Decimal("0.00")),
            ),
            Modifier(
                id=ModifierId("light_salt"),
                name="Light salt",
                price_delta=Money(Decimal("0.00")),
            ),
        ),
        min_selected=1,
        max_selected=1,
    )
    return MenuItem(
        id=MenuItemId("house_fries"),
        name="House Fries",
        base_price=Money(Decimal("4.00")),
        modifier_groups=(seasoning,),
    )


def _build_soda() -> MenuItem:
    return MenuItem(
        id=MenuItemId("house_soda"),
        name="House Soda",
        base_price=Money(Decimal("2.50")),
    )


def _build_demo_cart_lines(
    menu_item: MenuItem, fries: MenuItem
) -> tuple[CartLineDraftSnapshot, ...]:
    burger_modifiers = menu_item.validate_modifier_selections(
        (
            ModifierSelectionRequest(
                group_id=menu_item.modifier_groups[0].id,
                modifier_id=ModifierId("cheese"),
            ),
            ModifierSelectionRequest(
                group_id=menu_item.modifier_groups[0].id,
                modifier_id=ModifierId("onion"),
            ),
        )
    )
    burger_line = CartLineDraftSnapshot(
        line_id=CartLineId("cart_line_burger"),
        menu_item_id=menu_item.id,
        menu_item_name=menu_item.name,
        unit_price=menu_item.base_price,
        quantity=2,
        modifiers=burger_modifiers,
    )

    fries_modifiers = fries.validate_modifier_selections(
        (
            ModifierSelectionRequest(
                group_id=fries.modifier_groups[0].id,
                modifier_id=ModifierId("regular"),
            ),
        )
    )
    fries_line = CartLineDraftSnapshot(
        line_id=CartLineId("cart_line_fries"),
        menu_item_id=fries.id,
        menu_item_name=fries.name,
        unit_price=fries.base_price,
        quantity=1,
        modifiers=fries_modifiers,
    )

    return (burger_line, fries_line)


def seed_demo_data(session: Session) -> None:
    """Seed a realistic restaurant catalog and sample ordering flow."""

    restaurant_repo = RestaurantRepository(session)
    menu_repo = MenuRepository(session)
    customer_repo = CustomerRepository(session)
    call_repo = CallSessionRepository(session)
    cart_repo = CartRepository(session)
    order_repo = OrderRepository(session)
    payment_repo = PaymentRepository(session)
    payment_attempt_repo = PaymentAttemptRepository(session)
    payment_event_repo = PaymentEventRepository(session)
    idempotency_repo = IdempotencyRepository(session)
    outbox_repo = OutboxRepository(session)

    restaurant_repo.upsert(
        RestaurantRecord(
            id=RESTAURANT_ID.value,
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
            phone_number="+1-602-555-0148",
        )
    )

    burger = menu_repo.save_menu_item(RESTAURANT_ID, _build_burger())
    fries = menu_repo.save_menu_item(RESTAURANT_ID, _build_fries())
    menu_repo.save_menu_item(RESTAURANT_ID, _build_soda())

    customer_repo.upsert(
        CustomerRecord(
            id=CUSTOMER_ID.value,
            restaurant_id=RESTAURANT_ID.value,
            display_name="Maya Patel",
            phone_number="+1-602-555-0188",
            notes="Prefers no pickles.",
        )
    )

    call_repo.upsert(
        CallSessionRecord(
            id=CALL_SESSION_ID.value,
            restaurant_id=RESTAURANT_ID.value,
            customer_id=CUSTOMER_ID.value,
            provider_call_id="twilio_demo_call_001",
            channel="voice",
            status="COMPLETED",
            started_at=datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 7, 30, 18, 12, tzinfo=timezone.utc),
            notes="Demo call used for local development.",
        )
    )

    cart = cart_repo.upsert(
        CartRecord(
            id=CART_ID,
            restaurant_id=RESTAURANT_ID.value,
            customer_id=CUSTOMER_ID.value,
            call_session_id=CALL_SESSION_ID.value,
            status="SUBMITTED",
            source="voice",
        )
    )

    cart_lines = _build_demo_cart_lines(burger, fries)
    for line in cart_lines:
        cart_repo.save_line(cart.id, line)

    draft_cart = Cart(lines=tuple(cart_repo.list_lines(cart.id)))
    pricing = calculate_cart_pricing(draft_cart)
    submitted_lines = tuple(line.to_submitted_snapshot() for line in cart_repo.list_lines(cart.id))

    order_repo.upsert(
        OrderRecord(
            id=ORDER_ID.value,
            restaurant_id=RESTAURANT_ID.value,
            customer_id=CUSTOMER_ID.value,
            call_session_id=CALL_SESSION_ID.value,
            cart_id=cart.id,
            status=OrderStatus.CONFIRMED.value,
            subtotal_amount=pricing.subtotal.amount,
            subtotal_currency=pricing.subtotal.currency,
            confirmed_at=utcnow(),
            notes="Seeded order created from the demo cart.",
        )
    )
    order_repo.delete_lines(ORDER_ID.value)
    for line in submitted_lines:
        order_repo.save_line(ORDER_ID.value, line)

    payment_repo.upsert(
        PaymentRecord(
            id=PAYMENT_ID.value,
            order_id=ORDER_ID.value,
            status=PaymentStatus.PAID.value,
            provider="manual-seed",
            provider_reference="pi_demo_001",
            amount_amount=pricing.total.amount,
            amount_currency=pricing.total.currency,
            raw_payload={"source": "seed", "order_id": ORDER_ID.value},
            captured_at=utcnow(),
        )
    )

    payment_attempt = payment_attempt_repo.record_attempt(
        PaymentAttemptRecord(
            id="payment_attempt_demo_001",
            payment_id=PAYMENT_ID.value,
            attempt_number=1,
            provider="manual-seed",
            provider_reference="pi_demo_001_attempt_1",
            status=PaymentStatus.PAID.value,
            request_payload={"source": "seed", "order_id": ORDER_ID.value},
            response_payload={
                "payment_id": PAYMENT_ID.value,
                "status": PaymentStatus.PAID.value,
            },
        )
    )

    payment_event_repo.record_event(
        PaymentEventRecord(
            id="payment_event_demo_001",
            payment_id=PAYMENT_ID.value,
            payment_attempt_id=payment_attempt.id,
            provider_event_id="evt_demo_001",
            event_type="payment_intent.succeeded",
            payload={
                "event_id": "evt_demo_001",
                "payment_id": PAYMENT_ID.value,
                "status": PaymentStatus.PAID.value,
            },
        )
    )

    idempotency_repo.record_response(
        scope="checkout",
        key=CHECKOUT_IDEMPOTENCY_KEY,
        request_hash="seeded-demo-hash",
        response_status=200,
        response_body={"order_id": ORDER_ID.value, "status": OrderStatus.CONFIRMED.value},
    )

    outbox_repo.upsert(
        OutboxEventRecord(
            id=OUTBOX_EVENT_ID,
            aggregate_type="order",
            aggregate_id=ORDER_ID.value,
            event_type="order.confirmed",
            payload={
                "order_id": ORDER_ID.value,
                "restaurant_id": RESTAURANT_ID.value,
                "payment_id": PAYMENT_ID.value,
            },
        )
    )

    session.flush()


def main() -> int:
    """Seed the configured database with demo data."""

    settings = Settings()
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            seed_demo_data(session)
            session.commit()
        except Exception as exc:  # pragma: no cover - surfaced to CLI users
            session.rollback()
            raise SeedError("Failed to seed demo data") from exc
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
