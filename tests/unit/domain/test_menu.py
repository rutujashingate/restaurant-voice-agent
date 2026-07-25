"""Tests for menu items and modifier capture."""

import pytest

from restaurant_voice_agent.domain.errors import MenuError
from restaurant_voice_agent.domain.identifiers import MenuItemId, ModifierGroupId, ModifierId
from restaurant_voice_agent.domain.menu import (
    CapturedModifierSnapshot,
    MenuItem,
    Modifier,
    ModifierGroup,
    ModifierSelectionRequest,
)
from restaurant_voice_agent.domain.money import Money


def _build_burger_item(available: bool = True) -> MenuItem:
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
        available=available,
        allergens=("Wheat", "Dairy"),
    )


def test_menu_item_captures_modifier_snapshots() -> None:
    burger = _build_burger_item()
    group = burger.modifier_groups[0]

    captured = burger.validate_modifier_selections(
        (
            ModifierSelectionRequest(
                group_id=group.id,
                modifier_id=ModifierId("cheese"),
            ),
            ModifierSelectionRequest(
                group_id=group.id,
                modifier_id=ModifierId("onion"),
            ),
        )
    )

    assert len(captured) == 2
    assert isinstance(captured[0], CapturedModifierSnapshot)
    assert captured[0].group_name == "Burger toppings"
    assert captured[0].modifier_name == "Add cheese"
    assert captured[0].price_delta == Money("1.00")


def test_menu_item_rejects_unknown_modifier_group() -> None:
    burger = _build_burger_item()

    with pytest.raises(MenuError):
        burger.validate_modifier_selections(
            (
                ModifierSelectionRequest(
                    group_id=ModifierGroupId("other_group"),
                    modifier_id=ModifierId("cheese"),
                ),
            )
        )


def test_menu_item_rejects_sold_out_items() -> None:
    burger = _build_burger_item(available=False)

    with pytest.raises(MenuError):
        burger.validate_modifier_selections(())
