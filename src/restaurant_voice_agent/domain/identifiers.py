"""Typed identifier value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Type, TypeVar, cast
from uuid import uuid4

from .errors import IdentifierError

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TIdentifier = TypeVar("TIdentifier", bound="Identifier")


@dataclass(frozen=True)
class Identifier:
    """Base typed identifier wrapper."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise IdentifierError("Identifier values must be strings")

        candidate = self.value.strip()
        if not candidate:
            raise IdentifierError("Identifier values cannot be empty")
        if candidate != self.value:
            raise IdentifierError("Identifier values cannot have leading or trailing whitespace")
        if _IDENTIFIER_PATTERN.fullmatch(candidate) is None:
            raise IdentifierError(
                "Identifier values must use letters, numbers, underscores, or hyphens"
            )

    @classmethod
    def new(cls: Type[TIdentifier]) -> TIdentifier:
        """Create a new opaque identifier value."""

        return cast(TIdentifier, cls(uuid4().hex))

    def __str__(self) -> str:
        return self.value


class RestaurantId(Identifier):
    """Restaurant identifier."""


class CustomerId(Identifier):
    """Customer identifier."""


class CallSessionId(Identifier):
    """Call session identifier."""


class MenuItemId(Identifier):
    """Menu item identifier."""


class ModifierGroupId(Identifier):
    """Modifier group identifier."""


class ModifierId(Identifier):
    """Modifier identifier."""


class CartLineId(Identifier):
    """Cart line identifier."""


class OrderId(Identifier):
    """Order identifier."""


class PaymentId(Identifier):
    """Payment identifier."""


class ComplaintTicketId(Identifier):
    """Complaint ticket identifier."""


class HandoffId(Identifier):
    """Human handoff identifier."""
