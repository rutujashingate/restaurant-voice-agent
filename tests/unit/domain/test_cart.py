"""Tests for cart mutation, limits, and snapshots."""

import pytest

from restaurant_voice_agent.domain.cart import (
    MAX_CART_LINE_COUNT,
    MAX_CART_TOTAL_UNITS,
    MAX_LINE_QUANTITY,
    Cart,
    CartLineDraftSnapshot,
    SubmittedOrderLineSnapshot,
)
from restaurant_voice_agent.domain.errors import CartError, CartLimitError
from restaurant_voice_agent.domain.identifiers import (
    CartLineId,
    MenuItemId,
    ModifierGroupId,
    ModifierId,
)
from restaurant_voice_agent.domain.menu import (
    MenuItem,
    Modifier,
    ModifierGroup,
    ModifierSelectionRequest,
)
from restaurant_voice_agent.domain.money import Money


def _build_burger_item() -> MenuItem:
    toppings_group = ModifierGroup(
        id=ModifierGroupId("burger_toppings"),
        name="Burger toppings",
        modifiers=(
            Modifier(id=ModifierId("cheese"), name="Add cheese", price_delta=Money("1.00")),
            Modifier(id=ModifierId("onion"), name="No onion", price_delta=Money("0.00")),
            Modifier(id=ModifierId("pickle"), name="No pickle", price_delta=Money("0.00")),
        ),
        min_selected=0,
        max_selected=2,
    )
    return MenuItem(
        id=MenuItemId("classic_burger"),
        name="Classic Burger",
        base_price=Money("10.00"),
        modifier_groups=(toppings_group,),
    )


def _build_simple_item(index: int) -> MenuItem:
    return MenuItem(
        id=MenuItemId(f"item_{index}"),
        name=f"Item {index}",
        base_price=Money("1.00"),
    )


def _burger_cheese_request(burger: MenuItem) -> ModifierSelectionRequest:
    group = burger.modifier_groups[0]
    return ModifierSelectionRequest(group_id=group.id, modifier_id=ModifierId("cheese"))


def _burger_onion_request(burger: MenuItem) -> ModifierSelectionRequest:
    group = burger.modifier_groups[0]
    return ModifierSelectionRequest(group_id=group.id, modifier_id=ModifierId("onion"))


def test_cart_adds_items_and_merges_identical_lines() -> None:
    burger = _build_burger_item()
    cart = Cart.empty().add_item(
        burger,
        quantity=2,
        modifier_selections=(
            _burger_cheese_request(burger),
            _burger_onion_request(burger),
        ),
    )
    cart = cart.add_item(
        burger,
        quantity=1,
        modifier_selections=(
            _burger_cheese_request(burger),
            _burger_onion_request(burger),
        ),
    )

    assert cart.line_count == 1
    assert cart.total_units == 3
    assert cart.lines[0].quantity == 3


def test_cart_updates_quantity_and_removes_modifiers() -> None:
    burger = _build_burger_item()
    cart = Cart.empty().add_item(
        burger,
        quantity=1,
        modifier_selections=(
            _burger_cheese_request(burger),
            _burger_onion_request(burger),
        ),
    )
    line_id = cart.lines[0].line_id

    updated = cart.update_item(line_id, quantity=3)
    assert updated.lines[0].quantity == 3

    cleared_modifiers = updated.update_item(
        line_id,
        menu_item=burger,
        modifier_selections=(),
    )
    assert cleared_modifiers.lines[0].modifiers == ()


def test_cart_removes_items_and_clears() -> None:
    burger = _build_burger_item()
    cart = Cart.empty().add_item(burger)
    line_id = cart.lines[0].line_id

    removed = cart.remove_item(line_id)
    assert removed.line_count == 0
    assert removed.total_units == 0
    assert removed.clear().line_count == 0


def test_cart_rejects_quantity_and_size_limits() -> None:
    burger = _build_burger_item()
    with pytest.raises(CartLimitError):
        Cart.empty().add_item(burger, quantity=MAX_LINE_QUANTITY + 1)

    cart = Cart.empty()
    for index in range(MAX_CART_LINE_COUNT):
        cart = cart.add_item(_build_simple_item(index))

    assert cart.line_count == MAX_CART_LINE_COUNT

    with pytest.raises(CartLimitError):
        cart.add_item(_build_simple_item(999))

    large_cart = Cart.empty()
    for index in range(3):
        large_cart = large_cart.add_item(_build_simple_item(index), quantity=10)

    assert large_cart.total_units == MAX_CART_TOTAL_UNITS

    with pytest.raises(CartLimitError):
        large_cart.add_item(_build_simple_item(10))


def test_cart_rejects_sold_out_items() -> None:
    burger = _build_burger_item()
    sold_out = MenuItem(
        id=burger.id,
        name=burger.name,
        base_price=burger.base_price,
        modifier_groups=burger.modifier_groups,
        available=False,
    )

    with pytest.raises(CartError):
        Cart.empty().add_item(sold_out)


def test_draft_snapshot_converts_to_submitted_snapshot() -> None:
    burger = _build_burger_item()
    snapshot = CartLineDraftSnapshot(
        line_id=CartLineId.new(),
        menu_item_id=burger.id,
        menu_item_name=burger.name,
        unit_price=burger.base_price,
        quantity=2,
        modifiers=(),
    )

    submitted = snapshot.to_submitted_snapshot()

    assert isinstance(submitted, SubmittedOrderLineSnapshot)
    assert submitted.menu_item_name == "Classic Burger"
    assert submitted.quantity == 2
    assert submitted.line_total == Money("20.00")
