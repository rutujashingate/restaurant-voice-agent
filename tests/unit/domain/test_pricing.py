"""Tests for deterministic cart pricing."""

from decimal import Decimal

from restaurant_voice_agent.domain.cart import Cart
from restaurant_voice_agent.domain.identifiers import MenuItemId, ModifierGroupId, ModifierId
from restaurant_voice_agent.domain.menu import (
    MenuItem,
    Modifier,
    ModifierGroup,
    ModifierSelectionRequest,
)
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.domain.pricing import calculate_cart_pricing


def _build_burger_item() -> MenuItem:
    toppings_group = ModifierGroup(
        id=ModifierGroupId("burger_toppings"),
        name="Burger toppings",
        modifiers=(
            Modifier(id=ModifierId("cheese"), name="Add cheese", price_delta=Money("1.00")),
            Modifier(id=ModifierId("onion"), name="No onion", price_delta=Money("0.00")),
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


def test_pricing_excludes_tax_and_calculates_totals() -> None:
    burger = _build_burger_item()
    group = burger.modifier_groups[0]
    cart = Cart.empty().add_item(
        burger,
        quantity=2,
        modifier_selections=(
            ModifierSelectionRequest(group_id=group.id, modifier_id=ModifierId("cheese")),
        ),
    )

    breakdown = calculate_cart_pricing(cart)

    assert breakdown.item_subtotal.amount == Decimal("20.00")
    assert breakdown.modifier_subtotal.amount == Decimal("2.00")
    assert breakdown.subtotal.amount == Decimal("22.00")
    assert breakdown.total.amount == Decimal("22.00")
    assert not hasattr(breakdown, "tax")
