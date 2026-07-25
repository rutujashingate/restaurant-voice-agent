"""Domain enums for the restaurant voice agent."""

from __future__ import annotations

from enum import Enum


class AppEnvironment(str, Enum):
    """Deployment environment names."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class OrderStatus(str, Enum):
    """Authoritative order statuses."""

    DRAFT = "DRAFT"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    PAYMENT_EXPIRED = "PAYMENT_EXPIRED"


class PaymentStatus(str, Enum):
    """Authoritative payment statuses."""

    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class ComplaintCategory(str, Enum):
    """Supported complaint categories."""

    MISSING_ITEM = "MISSING_ITEM"
    WRONG_ITEM = "WRONG_ITEM"
    QUALITY_PROBLEM = "QUALITY_PROBLEM"
    LATE_ORDER = "LATE_ORDER"
    PAYMENT_PROBLEM = "PAYMENT_PROBLEM"
    DUPLICATE_CHARGE = "DUPLICATE_CHARGE"
    ALLERGY_CONCERN = "ALLERGY_CONCERN"
    STAFF_COMPLAINT = "STAFF_COMPLAINT"
    OTHER = "OTHER"


class TTSProvider(str, Enum):
    """Available text-to-speech providers."""

    ELEVENLABS = "elevenlabs"
    KOKORO = "kokoro"
