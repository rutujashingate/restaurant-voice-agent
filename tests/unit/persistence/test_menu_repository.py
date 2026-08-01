"""Tests for menu persistence and domain round-tripping."""

from __future__ import annotations

from restaurant_voice_agent.domain.identifiers import (
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    RestaurantId,
)
from restaurant_voice_agent.domain.menu import MenuItem, Modifier, ModifierGroup
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.models import RestaurantRecord
from restaurant_voice_agent.persistence.repositories import MenuRepository, RestaurantRepository


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
        allergens=("wheat", "dairy"),
    )


def test_menu_repository_round_trips_domain_menu(session) -> None:
    restaurant_repo = RestaurantRepository(session)
    menu_repo = MenuRepository(session)
    restaurant_id = RestaurantId("copper_spoon_kitchen")

    restaurant_repo.upsert(
        RestaurantRecord(
            id=restaurant_id.value,
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
        )
    )

    burger = build_burger()
    saved = menu_repo.save_menu_item(restaurant_id, burger)
    loaded = menu_repo.get_menu_item(burger.id.value)

    assert saved == burger
    assert loaded == burger
    assert menu_repo.list_menu_items(restaurant_id.value) == [burger]
