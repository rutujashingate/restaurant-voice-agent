"""Persistence-specific exceptions."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base class for persistence failures."""


class DatabaseConfigurationError(PersistenceError, ValueError):
    """Raised when a database URL is missing or invalid."""


class RepositoryError(PersistenceError):
    """Raised when a repository operation fails."""


class IdempotencyConflictError(RepositoryError):
    """Raised when a retry key is reused for a different request payload."""


class SeedError(PersistenceError):
    """Raised when demo seed data cannot be written."""
