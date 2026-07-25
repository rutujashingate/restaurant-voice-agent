"""Decimal money value object."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Union

from .errors import MoneyError

MONEY_QUANTUM = Decimal("0.01")
MoneyValue = Union[int, str, Decimal]
MoneyMultiplier = Union[int, Decimal]


def _coerce_decimal(value: MoneyValue) -> Decimal:
    if isinstance(value, bool):
        raise MoneyError("Boolean values are not valid money amounts")
    if isinstance(value, float):
        raise MoneyError("Float values are not valid money amounts")

    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, str):
        try:
            decimal_value = Decimal(value)
        except InvalidOperation as exc:
            raise MoneyError("String values must be valid decimal amounts") from exc
    else:
        raise MoneyError("Money must be constructed from Decimal, int, or string values")

    if not decimal_value.is_finite():
        raise MoneyError("Money amounts must be finite")
    return decimal_value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Money:
    """USD money amount backed by Decimal."""

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        amount = _coerce_decimal(self.amount)
        currency = self.currency
        if not isinstance(currency, str) or not currency:
            raise MoneyError("Currency must be a non-empty string")
        if len(currency) != 3 or currency.upper() != currency or not currency.isalpha():
            raise MoneyError("Currency must be a three-letter uppercase ISO code")

        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Return a zero-value money instance."""

        return cls(Decimal("0"), currency=currency)

    def _ensure_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise MoneyError("Money values must use the same currency")

    def __add__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, currency=self.currency)

    def __radd__(self, other: object) -> "Money":
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._ensure_same_currency(other)
        return Money(self.amount - other.amount, currency=self.currency)

    def __mul__(self, other: object) -> "Money":
        if isinstance(other, bool):
            raise MoneyError("Boolean multipliers are not valid")
        if isinstance(other, float):
            raise MoneyError("Float multipliers are not valid")
        if isinstance(other, int):
            multiplier = Decimal(other)
        elif isinstance(other, Decimal):
            multiplier = other
        else:
            return NotImplemented
        if not multiplier.is_finite():
            raise MoneyError("Money multipliers must be finite")
        return Money(self.amount * multiplier, currency=self.currency)

    def __rmul__(self, other: object) -> "Money":
        return self.__mul__(other)

    def __str__(self) -> str:
        return f"{self.currency} {format(self.amount, '.2f')}"
