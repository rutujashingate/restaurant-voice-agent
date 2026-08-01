"""Application-layer exceptions."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for application-service failures."""


class NotFoundError(ApplicationError):
    """Raised when a requested record or resource cannot be found."""


class ConflictError(ApplicationError):
    """Raised when a requested operation conflicts with current state."""


class PriceRevalidationError(ConflictError):
    """Raised when live menu prices or availability no longer match a draft cart."""


class CheckoutNotReadyError(ConflictError):
    """Raised when checkout cannot proceed yet."""


class PaymentVerificationError(ApplicationError):
    """Raised when a payment webhook or signature cannot be trusted."""


class CallLockError(ApplicationError):
    """Raised when a call is already being handled elsewhere."""


class ToolValidationError(ApplicationError, ValueError):
    """Raised when a typed tool input cannot be parsed."""
