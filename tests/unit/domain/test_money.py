"""Tests for the Decimal money value object."""

from decimal import Decimal

import pytest

from restaurant_voice_agent.domain.errors import MoneyError
from restaurant_voice_agent.domain.money import Money


def test_money_rejects_floats() -> None:
    with pytest.raises(MoneyError):
        Money(10.25)


def test_money_quantizes_half_up() -> None:
    assert Money("10.005").amount == Decimal("10.01")


def test_money_supports_addition_and_multiplication() -> None:
    subtotal = Money("10.00") + Money("2.50")
    doubled = Money("4.00") * 3

    assert subtotal.amount == Decimal("12.50")
    assert doubled.amount == Decimal("12.00")


def test_money_rejects_currency_mismatch() -> None:
    with pytest.raises(MoneyError):
        Money("1.00", currency="USD") + Money("1.00", currency="EUR")
