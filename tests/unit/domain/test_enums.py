"""Tests for enum values."""

from restaurant_voice_agent.domain.enums import (
    AppEnvironment,
    ComplaintCategory,
    OrderStatus,
    PaymentStatus,
    TTSProvider,
)


def test_order_status_values() -> None:
    assert OrderStatus.DRAFT.value == "DRAFT"
    assert OrderStatus.AWAITING_PAYMENT.value == "AWAITING_PAYMENT"
    assert OrderStatus.COMPLETED.value == "COMPLETED"


def test_payment_status_values() -> None:
    assert PaymentStatus.NOT_STARTED.value == "NOT_STARTED"
    assert PaymentStatus.PAID.value == "PAID"
    assert PaymentStatus.EXPIRED.value == "EXPIRED"


def test_complaint_category_values() -> None:
    assert ComplaintCategory.DUPLICATE_CHARGE.value == "DUPLICATE_CHARGE"
    assert ComplaintCategory.ALLERGY_CONCERN.value == "ALLERGY_CONCERN"


def test_environment_and_provider_values() -> None:
    assert AppEnvironment.DEVELOPMENT.value == "development"
    assert TTSProvider.ELEVENLABS.value == "elevenlabs"
    assert TTSProvider.KOKORO.value == "kokoro"
