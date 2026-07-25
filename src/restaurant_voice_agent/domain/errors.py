"""Domain-specific exceptions."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain failures."""


class ValidationError(DomainError, ValueError):
    """Raised when a domain object fails validation."""


class IdentifierError(ValidationError):
    """Raised when an identifier value is invalid."""


class MoneyError(ValidationError):
    """Raised when a money value is invalid."""


class MenuError(ValidationError):
    """Raised when a menu item or modifier selection is invalid."""


class CartError(ValidationError):
    """Raised when cart state or cart operations are invalid."""


class CartLimitError(CartError):
    """Raised when a cart limit is exceeded."""


class PricingError(DomainError, ValueError):
    """Raised when pricing cannot be computed."""
