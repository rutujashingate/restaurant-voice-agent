"""Protocol definitions for application services and external adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ContextManager, Protocol, TypeVar, runtime_checkable

from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.persistence.repositories import (
    CallSessionRepository,
    CartRepository,
    ComplaintRepository,
    CustomerRepository,
    HandoffRepository,
    IdempotencyRepository,
    MenuRepository,
    OrderRepository,
    OutboxRepository,
    PaymentAttemptRepository,
    PaymentEventRepository,
    PaymentRepository,
    RestaurantRepository,
)


class UnitOfWork(Protocol):
    """The repositories and transaction boundary required by the application layer."""

    session: Any
    restaurants: RestaurantRepository
    menu: MenuRepository
    customers: CustomerRepository
    calls: CallSessionRepository
    carts: CartRepository
    orders: OrderRepository
    payments: PaymentRepository
    payment_attempts: PaymentAttemptRepository
    payment_events: PaymentEventRepository
    complaints: ComplaintRepository
    handoffs: HandoffRepository
    idempotency: IdempotencyRepository
    outbox: OutboxRepository

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


@runtime_checkable
class Tool(Protocol[InputT, OutputT]):
    """A typed application tool callable from the workflow layer."""

    name: str
    description: str
    input_type: type[Any]

    def __call__(self, value: InputT) -> OutputT: ...


class SmsGateway(Protocol):
    """Send text notifications to a customer."""

    def send_sms(self, to_number: str, body: str) -> str: ...


class CheckoutGateway(Protocol):
    """Create a payment checkout link from a stored order total."""

    def create_checkout_link(
        self,
        *,
        order_id: str,
        amount: Money,
        customer_phone: str | None,
        metadata: Mapping[str, Any],
    ) -> str: ...


class WebhookVerifier(Protocol):
    """Verify a provider webhook signature."""

    def verify(self, *, payload: bytes, signature: str) -> bool: ...


class SpeechRecognizer(Protocol):
    """Convert audio payloads to text."""

    def transcribe(self, audio: bytes) -> str: ...


class SpeechSynthesizer(Protocol):
    """Convert text into an audio payload."""

    def synthesize(self, text: str) -> bytes: ...


class CallTransport(Protocol):
    """A call transport used by the live voice layer."""

    def start_call(self, call_id: str) -> None: ...

    def stop_call(self, call_id: str) -> None: ...

    def play_audio(self, call_id: str, audio: bytes) -> None: ...


class AudioInterruptionHandler(Protocol):
    """Handle barge-in or interruption events."""

    def interrupt(self, call_id: str) -> None: ...


class ConversationLockRegistry(Protocol):
    """Acquire and release a short-lived lock per call session."""

    def acquire(self, call_id: str) -> ContextManager[bool]: ...


class ConversationPlanner(Protocol):
    """Map user text to an intent and optional arguments."""

    def plan(self, text: str) -> str: ...


@dataclass(frozen=True)
class ProviderMessage:
    """A normalized outbound message to an external provider."""

    to: str
    body: str
    reference: str | None = None


@dataclass(frozen=True)
class CheckoutLinkRequest:
    """An outbound checkout request built from stored order state."""

    order_id: str
    amount: Money
    customer_phone: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class AudioPacket:
    """A normalized chunk of audio data."""

    call_id: str
    data: bytes


@dataclass(frozen=True)
class TranscriptEvent:
    """A normalized speech-to-text event."""

    call_id: str
    text: str


__all__ = [
    "AudioInterruptionHandler",
    "AudioPacket",
    "CallTransport",
    "CheckoutGateway",
    "CheckoutLinkRequest",
    "ConversationLockRegistry",
    "ConversationPlanner",
    "InputT",
    "OutputT",
    "ProviderMessage",
    "SmsGateway",
    "SpeechRecognizer",
    "SpeechSynthesizer",
    "Tool",
    "TranscriptEvent",
    "UnitOfWork",
    "WebhookVerifier",
]
