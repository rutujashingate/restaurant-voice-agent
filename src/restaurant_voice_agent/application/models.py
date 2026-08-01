"""Application-layer data transfer objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from restaurant_voice_agent.domain.cart import (
    Cart,
    CartLineDraftSnapshot,
    SubmittedOrderLineSnapshot,
)
from restaurant_voice_agent.domain.menu import MenuItem
from restaurant_voice_agent.domain.money import Money
from restaurant_voice_agent.domain.pricing import CartPricingBreakdown


def _empty_dict() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class MenuSearchHit:
    """A ranked menu-item search result."""

    item: MenuItem
    score: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriceRevalidationIssue:
    """A single issue discovered while re-checking a draft cart against live menu data."""

    line_id: str
    message: str
    captured_total: Money
    live_total: Money | None = None
    kind: str = "price_changed"


@dataclass(frozen=True)
class PriceRevalidationResult:
    """A cart that has been re-checked against live menu data."""

    cart: Cart
    quote: CartPricingBreakdown
    issues: tuple[PriceRevalidationIssue, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class CartSummary:
    """Human-readable cart snapshot used by tools and conversation state."""

    cart_id: str
    lines: tuple[CartLineDraftSnapshot, ...]
    quote: CartPricingBreakdown

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.lines)


@dataclass(frozen=True)
class CheckoutPreview:
    """A checkout-ready cart preview after price revalidation."""

    cart_id: str
    quote: CartPricingBreakdown
    issues: tuple[PriceRevalidationIssue, ...] = ()
    ready: bool = True
    message: str = "Cart is ready for checkout."


@dataclass(frozen=True)
class CheckoutSession:
    """A payment checkout session created from a confirmed cart."""

    order_id: str
    payment_id: str
    checkout_url: str
    amount: Money
    sms_body: str
    provider_reference: str
    provider_name: str
    metadata: dict[str, Any] = field(default_factory=_empty_dict)


@dataclass(frozen=True)
class OrderSummary:
    """A permanent order snapshot returned to callers."""

    order_id: str
    display_number: int
    status: str
    subtotal: Money
    cart_id: Optional[str] = None
    payment_status: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    lines: tuple[SubmittedOrderLineSnapshot, ...] = ()


@dataclass(frozen=True)
class PaymentWebhookResult:
    """Result of processing a payment provider event."""

    event_id: str
    order_id: str
    payment_id: str
    status: str
    duplicate: bool = False
    processed_at: Optional[datetime] = None


@dataclass(frozen=True)
class ComplaintSummary:
    """Customer complaint summary."""

    complaint_id: str
    display_number: int
    category: str
    status: str
    order_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class HandoffSummary:
    """Structured summary for a human handoff."""

    handoff_id: str
    status: str
    reason: str
    destination: Optional[str] = None
    order_id: Optional[str] = None
    complaint_id: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ConversationTurnResult:
    """A single assistant turn in the text or voice workflow."""

    reply_text: str
    topic: str
    cart_summary: Optional[CartSummary] = None
    order_summary: Optional[OrderSummary] = None
    checkout_session: Optional[CheckoutSession] = None
    complaint_summary: Optional[ComplaintSummary] = None
    handoff_summary: Optional[HandoffSummary] = None
    tool_outputs: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class EvaluationCase:
    """A scenario to run through the conversation engine."""

    name: str
    utterances: tuple[str, ...]
    expected_topics: tuple[str, ...] = ()
    expected_phrases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationCaseResult:
    """The outcome of running a single evaluation case."""

    case_name: str
    passed: bool
    transcript: tuple[ConversationTurnResult, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregate evaluation result."""

    name: str
    case_results: tuple[EvaluationCaseResult, ...]
    generated_at: datetime

    @property
    def passed(self) -> bool:
        return all(case_result.passed for case_result in self.case_results)

    @property
    def passed_count(self) -> int:
        return sum(1 for case_result in self.case_results if case_result.passed)

    @property
    def failed_count(self) -> int:
        return len(self.case_results) - self.passed_count


@dataclass(frozen=True)
class RedactionResult:
    """A redacted text snippet used for logs and evaluation output."""

    original: str
    redacted: str
