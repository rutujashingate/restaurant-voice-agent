"""Tests for typed identifiers."""

import pytest

from restaurant_voice_agent.domain.errors import IdentifierError
from restaurant_voice_agent.domain.identifiers import CartLineId, MenuItemId, ModifierId


def test_identifier_accepts_valid_value() -> None:
    identifier = MenuItemId("classic_burger")

    assert identifier.value == "classic_burger"
    assert str(identifier) == "classic_burger"


def test_identifier_rejects_empty_value() -> None:
    with pytest.raises(IdentifierError):
        MenuItemId("")


def test_identifier_rejects_whitespace_and_invalid_characters() -> None:
    with pytest.raises(IdentifierError):
        MenuItemId(" classic burger ")


def test_identifier_new_returns_typed_identifier() -> None:
    identifier = CartLineId.new()

    assert isinstance(identifier, CartLineId)
    assert identifier.value == str(identifier)


def test_identifier_types_do_not_compare_equal() -> None:
    assert MenuItemId("same_value") != ModifierId("same_value")
