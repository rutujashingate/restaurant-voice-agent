"""Menu, modifier, and selection domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from .errors import MenuError
from .identifiers import MenuItemId, ModifierGroupId, ModifierId
from .money import Money


@dataclass(frozen=True)
class ModifierSelectionRequest:
    """Transient selection input from a caller or model."""

    group_id: ModifierGroupId
    modifier_id: ModifierId


@dataclass(frozen=True)
class CapturedModifierSnapshot:
    """Immutable modifier snapshot captured from authoritative menu data."""

    group_id: ModifierGroupId
    group_name: str
    modifier_id: ModifierId
    modifier_name: str
    price_delta: Money

    def __post_init__(self) -> None:
        if not self.group_name.strip():
            raise MenuError("Modifier group name cannot be empty")
        if not self.modifier_name.strip():
            raise MenuError("Modifier name cannot be empty")
        if self.price_delta.amount < 0:
            raise MenuError("Modifier prices cannot be negative")
        if self.price_delta.currency != "USD":
            raise MenuError("Modifier prices must be stored in USD")


@dataclass(frozen=True)
class Modifier:
    """Menu modifier with a deterministic price delta."""

    id: ModifierId
    name: str
    price_delta: Money = field(default_factory=Money.zero)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MenuError("Modifier name cannot be empty")
        if self.price_delta.amount < 0:
            raise MenuError("Modifier price deltas cannot be negative")
        if self.price_delta.currency != "USD":
            raise MenuError("Modifier prices must be stored in USD")


@dataclass(frozen=True)
class ModifierGroup:
    """A modifier group with explicit cardinality rules."""

    id: ModifierGroupId
    name: str
    modifiers: Tuple[Modifier, ...]
    min_selected: int = 0
    max_selected: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MenuError("Modifier group name cannot be empty")
        if not self.modifiers:
            raise MenuError("Modifier groups must contain at least one modifier")
        if self.min_selected < 0:
            raise MenuError("Modifier group minimum selection cannot be negative")
        if self.max_selected < 1:
            raise MenuError("Modifier group maximum selection must be at least one")
        if self.min_selected > self.max_selected:
            raise MenuError("Modifier group minimum selection cannot exceed the maximum")
        if self.max_selected > len(self.modifiers):
            raise MenuError("Modifier group maximum selection cannot exceed available modifiers")

        modifier_ids = [modifier.id for modifier in self.modifiers]
        if len(modifier_ids) != len(set(modifier_ids)):
            raise MenuError("Modifier groups cannot contain duplicate modifier identifiers")

    def modifier_by_id(self, modifier_id: ModifierId) -> Modifier:
        for modifier in self.modifiers:
            if modifier.id == modifier_id:
                return modifier
        raise MenuError("Unknown modifier selected for group")

    def validate_selection(
        self, selections: Sequence[ModifierSelectionRequest]
    ) -> Tuple[CapturedModifierSnapshot, ...]:
        selection_list = list(selections)
        if len(selection_list) < self.min_selected:
            raise MenuError("Too few modifiers selected for this group")
        if len(selection_list) > self.max_selected:
            raise MenuError("Too many modifiers selected for this group")

        seen_modifier_ids: set[ModifierId] = set()
        captured: list[CapturedModifierSnapshot] = []
        for selection in selection_list:
            if selection.group_id != self.id:
                raise MenuError("Selection references the wrong modifier group")
            if selection.modifier_id in seen_modifier_ids:
                raise MenuError("Duplicate modifier selections are not allowed")
            seen_modifier_ids.add(selection.modifier_id)
            modifier = self.modifier_by_id(selection.modifier_id)
            captured.append(
                CapturedModifierSnapshot(
                    group_id=self.id,
                    group_name=self.name,
                    modifier_id=modifier.id,
                    modifier_name=modifier.name,
                    price_delta=modifier.price_delta,
                )
            )
        return tuple(captured)


@dataclass(frozen=True)
class MenuItem:
    """Menu item that can be added to a cart."""

    id: MenuItemId
    name: str
    base_price: Money
    modifier_groups: Tuple[ModifierGroup, ...] = ()
    available: bool = True
    description: Optional[str] = None
    allergens: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MenuError("Menu item name cannot be empty")
        if self.base_price.amount < 0:
            raise MenuError("Menu item prices cannot be negative")
        if self.base_price.currency != "USD":
            raise MenuError("Menu item prices must be stored in USD")
        if self.description is not None and not self.description.strip():
            raise MenuError("Menu item descriptions cannot be blank")

        group_ids = [group.id for group in self.modifier_groups]
        if len(group_ids) != len(set(group_ids)):
            raise MenuError("Menu items cannot contain duplicate modifier groups")

        cleaned_allergens: list[str] = []
        for allergen in self.allergens:
            if not allergen.strip():
                raise MenuError("Allergen entries cannot be blank")
            cleaned_allergens.append(allergen.strip())
        object.__setattr__(self, "allergens", tuple(cleaned_allergens))

    def modifier_group_by_id(self, group_id: ModifierGroupId) -> ModifierGroup:
        for group in self.modifier_groups:
            if group.id == group_id:
                return group
        raise MenuError("Unknown modifier group for this menu item")

    def validate_modifier_selections(
        self, selections: Sequence[ModifierSelectionRequest]
    ) -> Tuple[CapturedModifierSnapshot, ...]:
        if not self.available:
            raise MenuError("Sold-out menu items cannot be added to the cart")

        selection_list = list(selections)
        grouped_selections: dict[ModifierGroupId, list[ModifierSelectionRequest]] = {}
        for selection in selection_list:
            grouped_selections.setdefault(selection.group_id, []).append(selection)

        unknown_groups: set[ModifierGroupId] = set(grouped_selections) - {
            group.id for group in self.modifier_groups
        }
        if unknown_groups:
            raise MenuError("Unknown modifier group selected for menu item")

        captured: list[CapturedModifierSnapshot] = []
        for group in self.modifier_groups:
            group_selections: list[ModifierSelectionRequest] = grouped_selections.get(group.id, [])
            captured.extend(group.validate_selection(group_selections))

        return tuple(captured)

    def capture_modifier_names(self) -> Tuple[str, ...]:
        return tuple(group.name for group in self.modifier_groups)
