"""Tests for cart operations, checkout revalidation, and order snapshots."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from restaurant_voice_agent.application.cart import CartContext, CartService
from restaurant_voice_agent.application.catalog import PriceRevalidationService
from restaurant_voice_agent.application.errors import PriceRevalidationError
from restaurant_voice_agent.application.orders import OrderService
from restaurant_voice_agent.domain.cart import CartLineDraftSnapshot, SubmittedOrderLineSnapshot
from restaurant_voice_agent.domain.identifiers import ModifierId
from restaurant_voice_agent.domain.menu import ModifierSelectionRequest
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.repositories import MenuRepository

from .helpers import seed_restaurant_catalog


def _add_cheese(cart_service: CartService, cart_id: str, restaurant_id: str, burger) -> None:
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


def test_cart_service_add_update_and_remove(uow_factory, session) -> None:
    restaurant_id, burger, _ = seed_restaurant_catalog(session)
    cart_service = CartService(uow_factory)
    cart_id = "cart_demo"

    created = cart_service.create_cart(
        CartContext(cart_id=cart_id, restaurant_id=restaurant_id, source="voice")
    )
    assert created.line_count == 0

    added = cart_service.add_item(
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
    assert added.line_count == 1
    assert added.total_units == 1

    updated = cart_service.update_item(
        cart_id,
        restaurant_id,
        added.lines[0].line_id,
        quantity=2,
    )
    assert updated.lines[0].quantity == 2
    assert updated.total_units == 2

    removed = cart_service.remove_item(cart_id, restaurant_id, updated.lines[0].line_id)
    assert removed.line_count == 0


def test_order_service_revalidates_prices_before_confirmation(uow_factory, session) -> None:
    restaurant_id, burger, _ = seed_restaurant_catalog(session)
    cart_service = CartService(uow_factory)
    order_service = OrderService(
        uow_factory,
        cart_service=cart_service,
        price_revalidation_service=PriceRevalidationService(uow_factory),
    )
    cart_id = "cart_price_check"

    cart_service.create_cart(CartContext(cart_id=cart_id, restaurant_id=restaurant_id))
    _add_cheese(cart_service, cart_id, restaurant_id, burger)

    preview = order_service.preview_checkout(cart_id, restaurant_id)
    assert preview.ready is True
    assert preview.quote.total.amount == Decimal("11.00")

    menu_repo = MenuRepository(session)
    menu_repo.save_menu_item(
        restaurant_id,
        replace(burger, base_price=Money(Decimal("12.00"))),
    )

    changed_preview = order_service.preview_checkout(cart_id, restaurant_id)
    assert changed_preview.ready is False
    assert changed_preview.issues
    assert changed_preview.issues[0].kind == "price_changed"

    with pytest.raises(PriceRevalidationError):
        order_service.confirm_cart(cart_id=cart_id, restaurant_id=restaurant_id)


def test_order_service_persists_permanent_order_snapshots(uow_factory, session) -> None:
    restaurant_id, burger, _ = seed_restaurant_catalog(session)
    cart_service = CartService(uow_factory)
    order_service = OrderService(uow_factory, cart_service=cart_service)
    cart_id = "cart_snapshot"

    cart_service.create_cart(CartContext(cart_id=cart_id, restaurant_id=restaurant_id))
    _add_cheese(cart_service, cart_id, restaurant_id, burger)

    confirmed = order_service.confirm_cart(cart_id=cart_id, restaurant_id=restaurant_id)

    with uow_factory() as uow:
        cart_lines = uow.carts.list_lines(cart_id)
        order_lines = uow.orders.list_lines(confirmed.summary.order_id)

    assert isinstance(cart_lines[0], CartLineDraftSnapshot)
    assert isinstance(order_lines[0], SubmittedOrderLineSnapshot)
    assert cart_lines[0].line_total == order_lines[0].line_total
    assert cart_lines[0].to_submitted_snapshot() == order_lines[0]
