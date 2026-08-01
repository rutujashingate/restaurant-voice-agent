"""Shared helpers for application-layer unit tests."""

from __future__ import annotations

from decimal import Decimal

from restaurant_voice_agent.domain.identifiers import (
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    RestaurantId,
)
from restaurant_voice_agent.domain.menu import MenuItem, Modifier, ModifierGroup
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.models import CustomerRecord, RestaurantRecord
from restaurant_voice_agent.persistence.repositories import MenuRepository, RestaurantRepository

RESTAURANT_ID = RestaurantId("copper_spoon_kitchen")
CUSTOMER_ID = "maya_patel"
CUSTOMER_PHONE = "+1-602-555-0188"


def build_burger() -> MenuItem:
    """Build a simple burger item with a topping group."""

    toppings = ModifierGroup(
        id=ModifierGroupId("burger_toppings"),
        name="Burger toppings",
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
        ),
        min_selected=0,
        max_selected=1,
    )
    return MenuItem(
        id=MenuItemId("classic_burger"),
        name="Classic Burger",
        base_price=Money(Decimal("10.00")),
        modifier_groups=(toppings,),
        allergens=("wheat", "dairy"),
    )


def build_fries() -> MenuItem:
    """Build a simple fries item."""

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
                id=ModifierId("light"),
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


def seed_restaurant_catalog(session) -> tuple[str, MenuItem, MenuItem]:
    """Insert one restaurant and a small sample menu."""

    restaurant_repo = RestaurantRepository(session)
    menu_repo = MenuRepository(session)

    restaurant_repo.upsert(
        RestaurantRecord(
            id=RESTAURANT_ID.value,
            name="Copper Spoon Kitchen",
            timezone="America/Phoenix",
            phone_number="+1-602-555-0148",
        )
    )

    burger = menu_repo.save_menu_item(RESTAURANT_ID, build_burger())
    fries = menu_repo.save_menu_item(RESTAURANT_ID, build_fries())
    session.commit()
    return RESTAURANT_ID.value, burger, fries


def seed_customer(session, restaurant_id: str = RESTAURANT_ID.value) -> str:
    """Insert a sample customer record."""

    session.add(
        CustomerRecord(
            id=CUSTOMER_ID,
            restaurant_id=restaurant_id,
            display_name="Maya Patel",
            phone_number=CUSTOMER_PHONE,
            notes="Prefers no pickles.",
        )
    )
    session.commit()
    return CUSTOMER_ID
