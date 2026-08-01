"""Tests for draft cart snapshots and permanent order snapshots."""

from __future__ import annotations

from restaurant_voice_agent.domain.cart import (
    Cart,
    CartLineDraftSnapshot,
    SubmittedOrderLineSnapshot,
)
from restaurant_voice_agent.domain.identifiers import (
    CartLineId,
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    OrderId,
)
from restaurant_voice_agent.domain.menu import (
    MenuItem,
    Modifier,
    ModifierGroup,
    ModifierSelectionRequest,
)
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.domain.pricing import calculate_cart_pricing
from restaurant_voice_agent.persistence.models import CartRecord, OrderRecord, RestaurantRecord
from restaurant_voice_agent.persistence.repositories import (
    CartRepository,
    MenuRepository,
    OrderRepository,
    RestaurantRepository,
)


def build_burger() -> MenuItem:
    toppings = ModifierGroup(
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
        modifier_groups=(toppings,),
    )


def build_burger_line(burger: MenuItem) -> CartLineDraftSnapshot:
    group = burger.modifier_groups[0]
    modifiers = burger.validate_modifier_selections(
        (
            ModifierSelectionRequest(group_id=group.id, modifier_id=ModifierId("cheese")),
            ModifierSelectionRequest(group_id=group.id, modifier_id=ModifierId("onion")),
        )
    )
    return CartLineDraftSnapshot(
        line_id=CartLineId("cart_line_burger"),
        menu_item_id=burger.id,
        menu_item_name=burger.name,
        unit_price=burger.base_price,
        quantity=2,
        modifiers=modifiers,
    )


def test_cart_and_order_repositories_store_separate_snapshots(session) -> None:
    restaurant_repo = RestaurantRepository(session)
    menu_repo = MenuRepository(session)
    cart_repo = CartRepository(session)
    order_repo = OrderRepository(session)

    restaurant_repo.upsert(
        RestaurantRecord(
            id="copper_spoon_kitchen",
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
        )
    )

    restaurant = restaurant_repo.get("copper_spoon_kitchen")
    assert restaurant is not None

    burger = menu_repo.save_menu_item(
        restaurant_id=restaurant.id,
        menu_item=build_burger(),
    )
    draft_line = build_burger_line(burger)

    cart = cart_repo.upsert(
        CartRecord(
            id="cart_demo",
            restaurant_id="copper_spoon_kitchen",
            status="OPEN",
            source="voice",
        )
    )
    cart_repo.save_line(cart.id, draft_line)

    loaded_draft_lines = cart_repo.list_lines(cart.id)
    draft_cart = Cart(lines=tuple(loaded_draft_lines))
    pricing = calculate_cart_pricing(draft_cart)

    order = order_repo.upsert(
        OrderRecord(
            id=OrderId("order_demo").value,
            restaurant_id="copper_spoon_kitchen",
            cart_id=cart.id,
            status="CONFIRMED",
            subtotal_amount=pricing.total.amount,
            subtotal_currency=pricing.total.currency,
        )
    )
    order_repo.save_line(order.id, draft_line.to_submitted_snapshot())

    loaded_order_lines = order_repo.list_lines(order.id)

    assert isinstance(loaded_draft_lines[0], CartLineDraftSnapshot)
    assert isinstance(loaded_order_lines[0], SubmittedOrderLineSnapshot)
    assert loaded_draft_lines[0].menu_item_name == loaded_order_lines[0].menu_item_name
    assert loaded_draft_lines[0].line_total == loaded_order_lines[0].line_total
    assert loaded_draft_lines[0].to_submitted_snapshot() == loaded_order_lines[0]
