"""Helpers for converting between domain objects and ORM records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from restaurant_voice_agent.domain.cart import (
    CartLineDraftSnapshot,
    SubmittedOrderLineSnapshot,
)
from restaurant_voice_agent.domain.identifiers import (
    CartLineId,
    MenuItemId,
    ModifierGroupId,
    ModifierId,
    RestaurantId,
)
from restaurant_voice_agent.domain.menu import (
    CapturedModifierSnapshot,
    MenuItem,
    Modifier,
    ModifierGroup,
)
from restaurant_voice_agent.domain.money import Money

from .models import (
    CartLineRecord,
    MenuItemRecord,
    ModifierGroupRecord,
    ModifierRecord,
    OrderLineRecord,
)


def money_to_payload(value: Money) -> dict[str, str]:
    """Serialize money values into JSON-safe data."""

    return {"amount": str(value.amount), "currency": value.currency}


def money_from_payload(payload: Mapping[str, Any]) -> Money:
    """Deserialize a JSON-safe money payload."""

    return Money(payload["amount"], currency=payload["currency"])


def modifier_snapshot_to_payload(snapshot: CapturedModifierSnapshot) -> dict[str, str]:
    """Serialize a captured modifier snapshot."""

    return {
        "group_id": snapshot.group_id.value,
        "group_name": snapshot.group_name,
        "modifier_id": snapshot.modifier_id.value,
        "modifier_name": snapshot.modifier_name,
        "price_delta_amount": str(snapshot.price_delta.amount),
        "price_delta_currency": snapshot.price_delta.currency,
    }


def modifier_snapshot_from_payload(payload: Mapping[str, Any]) -> CapturedModifierSnapshot:
    """Deserialize a captured modifier snapshot."""

    return CapturedModifierSnapshot(
        group_id=ModifierGroupId(payload["group_id"]),
        group_name=payload["group_name"],
        modifier_id=ModifierId(payload["modifier_id"]),
        modifier_name=payload["modifier_name"],
        price_delta=Money(payload["price_delta_amount"], currency=payload["price_delta_currency"]),
    )


def modifiers_to_payload(
    modifiers: Sequence[CapturedModifierSnapshot],
) -> list[dict[str, str]]:
    """Serialize a collection of modifier snapshots."""

    return [modifier_snapshot_to_payload(modifier) for modifier in modifiers]


def modifiers_from_payload(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[CapturedModifierSnapshot, ...]:
    """Deserialize a collection of modifier snapshots."""

    return tuple(modifier_snapshot_from_payload(item) for item in payload)


def menu_item_to_record(restaurant_id: RestaurantId | str, menu_item: MenuItem) -> MenuItemRecord:
    """Convert a domain menu item into an ORM graph."""

    restaurant_id_value = (
        restaurant_id.value if isinstance(restaurant_id, RestaurantId) else restaurant_id
    )
    return MenuItemRecord(
        id=menu_item.id.value,
        restaurant_id=restaurant_id_value,
        name=menu_item.name,
        description=menu_item.description,
        base_price_amount=menu_item.base_price.amount,
        base_price_currency=menu_item.base_price.currency,
        available=menu_item.available,
        allergens=list(menu_item.allergens),
        modifier_groups=[
            ModifierGroupRecord(
                id=group.id.value,
                name=group.name,
                min_selected=group.min_selected,
                max_selected=group.max_selected,
                sort_order=index,
                modifiers=[
                    ModifierRecord(
                        id=modifier.id.value,
                        name=modifier.name,
                        price_delta_amount=modifier.price_delta.amount,
                        price_delta_currency=modifier.price_delta.currency,
                        available=True,
                        sort_order=modifier_index,
                    )
                    for modifier_index, modifier in enumerate(group.modifiers)
                ],
            )
            for index, group in enumerate(menu_item.modifier_groups)
        ],
    )


def menu_item_from_record(record: MenuItemRecord) -> MenuItem:
    """Convert an ORM menu item graph into the domain model."""

    groups = tuple(
        ModifierGroup(
            id=ModifierGroupId(group.id),
            name=group.name,
            modifiers=tuple(
                Modifier(
                    id=ModifierId(modifier.id),
                    name=modifier.name,
                    price_delta=Money(
                        modifier.price_delta_amount, currency=modifier.price_delta_currency
                    ),
                )
                for modifier in sorted(group.modifiers, key=lambda item: (item.sort_order, item.id))
            ),
            min_selected=group.min_selected,
            max_selected=group.max_selected,
        )
        for group in sorted(record.modifier_groups, key=lambda item: (item.sort_order, item.id))
    )
    return MenuItem(
        id=MenuItemId(record.id),
        name=record.name,
        base_price=Money(record.base_price_amount, currency=record.base_price_currency),
        modifier_groups=groups,
        available=record.available,
        description=record.description,
        allergens=tuple(record.allergens or ()),
    )


def cart_line_to_record(cart_id: str, line: CartLineDraftSnapshot) -> CartLineRecord:
    """Convert a draft snapshot into an ORM cart line."""

    return CartLineRecord(
        id=line.line_id.value,
        cart_id=cart_id,
        menu_item_id=line.menu_item_id.value,
        menu_item_name=line.menu_item_name,
        unit_price_amount=line.unit_price.amount,
        unit_price_currency=line.unit_price.currency,
        quantity=line.quantity,
        modifiers=modifiers_to_payload(line.modifiers),
    )


def cart_line_from_record(record: CartLineRecord) -> CartLineDraftSnapshot:
    """Convert an ORM cart line into a draft snapshot."""

    return CartLineDraftSnapshot(
        line_id=CartLineId(record.id),
        menu_item_id=MenuItemId(record.menu_item_id),
        menu_item_name=record.menu_item_name,
        unit_price=Money(record.unit_price_amount, currency=record.unit_price_currency),
        quantity=record.quantity,
        modifiers=modifiers_from_payload(record.modifiers),
    )


def order_line_to_record(order_id: str, line: SubmittedOrderLineSnapshot) -> OrderLineRecord:
    """Convert a submitted snapshot into an ORM order line."""

    return OrderLineRecord(
        id=line.line_id.value,
        order_id=order_id,
        menu_item_id=line.menu_item_id.value,
        menu_item_name=line.menu_item_name,
        unit_price_amount=line.unit_price.amount,
        unit_price_currency=line.unit_price.currency,
        quantity=line.quantity,
        modifiers=modifiers_to_payload(line.modifiers),
    )


def order_line_from_record(record: OrderLineRecord) -> SubmittedOrderLineSnapshot:
    """Convert an ORM order line into a submitted snapshot."""

    return SubmittedOrderLineSnapshot(
        line_id=CartLineId(record.id),
        menu_item_id=MenuItemId(record.menu_item_id),
        menu_item_name=record.menu_item_name,
        unit_price=Money(record.unit_price_amount, currency=record.unit_price_currency),
        quantity=record.quantity,
        modifiers=modifiers_from_payload(record.modifiers),
    )
