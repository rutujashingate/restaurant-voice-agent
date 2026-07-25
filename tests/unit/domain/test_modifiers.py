"""Tests for modifier groups and cardinality rules."""

import pytest

from restaurant_voice_agent.domain.errors import MenuError
from restaurant_voice_agent.domain.identifiers import ModifierGroupId, ModifierId
from restaurant_voice_agent.domain.menu import Modifier, ModifierGroup, ModifierSelectionRequest
from restaurant_voice_agent.domain.money import Money


def _build_required_group() -> ModifierGroup:
    return ModifierGroup(
        id=ModifierGroupId("size"),
        name="Size",
        modifiers=(
            Modifier(id=ModifierId("small"), name="Small", price_delta=Money("0.00")),
            Modifier(id=ModifierId("large"), name="Large", price_delta=Money("2.00")),
        ),
        min_selected=1,
        max_selected=1,
    )


def _build_optional_group() -> ModifierGroup:
    return ModifierGroup(
        id=ModifierGroupId("toppings"),
        name="Toppings",
        modifiers=(
            Modifier(id=ModifierId("cheese"), name="Add cheese", price_delta=Money("1.00")),
            Modifier(id=ModifierId("onion"), name="No onion", price_delta=Money("0.00")),
            Modifier(id=ModifierId("pickle"), name="No pickle", price_delta=Money("0.00")),
        ),
        min_selected=0,
        max_selected=2,
    )


def test_modifier_group_requires_valid_cardinality_bounds() -> None:
    with pytest.raises(MenuError):
        ModifierGroup(
            id=ModifierGroupId("bad"),
            name="Bad",
            modifiers=(
                Modifier(id=ModifierId("a"), name="A", price_delta=Money("0.00")),
                Modifier(id=ModifierId("b"), name="B", price_delta=Money("0.00")),
            ),
            min_selected=2,
            max_selected=1,
        )

    with pytest.raises(MenuError):
        ModifierGroup(
            id=ModifierGroupId("too_many"),
            name="Too many",
            modifiers=(
                Modifier(id=ModifierId("a"), name="A", price_delta=Money("0.00")),
                Modifier(id=ModifierId("b"), name="B", price_delta=Money("0.00")),
            ),
            min_selected=0,
            max_selected=3,
        )


def test_required_modifier_group_rejects_empty_selection() -> None:
    group = _build_required_group()

    with pytest.raises(MenuError):
        group.validate_selection(())


def test_optional_modifier_group_allows_multiple_selections() -> None:
    group = _build_optional_group()

    captured = group.validate_selection(
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
    assert captured[0].modifier_name == "Add cheese"
    assert captured[1].modifier_name == "No onion"


def test_modifier_group_rejects_duplicate_selection() -> None:
    group = _build_optional_group()

    with pytest.raises(MenuError):
        group.validate_selection(
            (
                ModifierSelectionRequest(
                    group_id=group.id,
                    modifier_id=ModifierId("cheese"),
                ),
                ModifierSelectionRequest(
                    group_id=group.id,
                    modifier_id=ModifierId("cheese"),
                ),
            )
        )
