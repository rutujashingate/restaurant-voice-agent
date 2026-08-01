"""Text conversation workflow for the restaurant voice agent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum

from restaurant_voice_agent.application.cart import CartContext, CartService
from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.models import (
    CartSummary,
    CheckoutPreview,
    CheckoutSession,
    ConversationTurnResult,
    MenuSearchHit,
)
from restaurant_voice_agent.application.tools import (
    ConfirmCartInput,
    CreateCheckoutSessionInput,
    CreateComplaintInput,
    CreateHandoffInput,
    LookupOrderInput,
    PreviewCheckoutInput,
    SearchMenuInput,
    Toolset,
)
from restaurant_voice_agent.domain.cart import CartLineDraftSnapshot
from restaurant_voice_agent.domain.menu import MenuItem, ModifierSelectionRequest


class ConversationIntent(str, Enum):
    """High-level topics the workflow understands."""

    GREETING = "greeting"
    MENU = "menu"
    ADD_ITEM = "add_item"
    UPDATE_ITEM = "update_item"
    REMOVE_ITEM = "remove_item"
    REVIEW_CART = "review_cart"
    CONFIRM_CHECKOUT = "confirm_checkout"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    HANDOFF = "handoff"
    PAYMENT_WEBHOOK = "payment_webhook"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConversationTurn:
    """A single transcript entry."""

    speaker: str
    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ConversationState:
    """Safe in-memory call state."""

    call_session_id: str
    restaurant_id: str
    customer_id: str | None = None
    customer_phone: str | None = None
    cart_id: str | None = None
    order_id: str | None = None
    last_intent: ConversationIntent = ConversationIntent.GREETING
    pending_checkout: CheckoutPreview | None = None
    last_checkout: CheckoutSession | None = None
    transcript: tuple[ConversationTurn, ...] = ()


class RuleBasedPlanner:
    """A lightweight planner that routes text into the right workflow branch."""

    _intent_patterns: tuple[tuple[ConversationIntent, tuple[str, ...]], ...] = (
        (
            ConversationIntent.MENU,
            ("what do you have", "menu", "what's on", "show me", "what can i order"),
        ),
        (
            ConversationIntent.ORDER_STATUS,
            ("order status", "where is my order", "status", "track", "pickup"),
        ),
        (
            ConversationIntent.ADD_ITEM,
            ("add ", "i want ", "get me ", "can i have ", "i'd like "),
        ),
        (
            ConversationIntent.UPDATE_ITEM,
            ("change ", "update ", "make it ", "increase ", "decrease "),
        ),
        (
            ConversationIntent.REMOVE_ITEM,
            ("remove ", "delete ", "take off ", "no ", "actually no"),
        ),
        (
            ConversationIntent.REVIEW_CART,
            ("cart", "subtotal", "total", "review", "what's in my order"),
        ),
        (
            ConversationIntent.CONFIRM_CHECKOUT,
            ("checkout", "confirm", "looks good", "that's right", "yes", "proceed"),
        ),
        (
            ConversationIntent.COMPLAINT,
            ("complaint", "problem", "issue", "wrong", "missing", "late", "allergy"),
        ),
        (
            ConversationIntent.HANDOFF,
            ("manager", "human", "person", "operator", "agent"),
        ),
        (
            ConversationIntent.PAYMENT_WEBHOOK,
            ("payment succeeded", "payment failed", "webhook", "checkout paid"),
        ),
    )

    def plan(self, text: str) -> str:
        lowered = text.lower().strip()
        for intent, phrases in self._intent_patterns:
            if any(phrase in lowered for phrase in phrases):
                return intent.value
        return ConversationIntent.UNKNOWN.value


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _extract_quantity(text: str) -> int:
    match = re.search(r"\b([1-9]|10)\b", text)
    if match:
        return int(match.group(1))
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return 1


def _affirmative(text: str) -> bool:
    lowered = text.lower()
    return (
        any(
            phrase in lowered
            for phrase in (
                " yes",
                "confirm",
                "looks good",
                "that's right",
                "proceed",
            )
        )
        or re.search(r"\byes\b", lowered) is not None
    )


def _line_description(line: CartLineDraftSnapshot) -> str:
    modifier_text = ", ".join(modifier.modifier_name for modifier in line.modifiers)
    if modifier_text:
        modifier_text = f" with {modifier_text}"
    return f"{line.quantity} x {line.menu_item_name}{modifier_text}"


def _cart_summary_text(summary: CartSummary) -> str:
    if not summary.lines:
        return f"Cart {summary.cart_id} is empty."
    line_descriptions = "; ".join(_line_description(line) for line in summary.lines)
    return (
        f"Cart {summary.cart_id} has {summary.line_count} item(s): "
        f"{line_descriptions}. Total is {summary.quote.total}."
    )


def _extract_modifier_selections(
    item: MenuItem, user_text: str
) -> tuple[ModifierSelectionRequest, ...]:
    tokens = set(_tokenize(user_text))
    selections: list[ModifierSelectionRequest] = []
    for group in item.modifier_groups:
        selected = [
            modifier
            for modifier in group.modifiers
            if modifier.id.value.lower() in tokens or modifier.name.lower() in user_text.lower()
        ]
        if not selected and group.min_selected > 0:
            selected = list(group.modifiers[: group.min_selected])
        for modifier in selected[: group.max_selected]:
            selections.append(ModifierSelectionRequest(group_id=group.id, modifier_id=modifier.id))
    return tuple(selections)


def _extract_item_query(text: str) -> str:
    lowered = text.lower()
    for prefix in ("add", "order", "i want", "get me", "can i have", "i'd like"):
        lowered = lowered.replace(prefix, "")
    return " ".join(_tokenize(lowered))


class ConversationWorkflow:
    """A reusable per-call conversation workflow."""

    def __init__(
        self,
        *,
        toolset: Toolset,
        cart_service: CartService,
        call_session_id: str,
        restaurant_id: str,
        customer_id: str | None = None,
        customer_phone: str | None = None,
        planner: RuleBasedPlanner | None = None,
    ) -> None:
        self.toolset = toolset
        self.cart_service = cart_service
        self.planner = planner or RuleBasedPlanner()
        self.state = ConversationState(
            call_session_id=call_session_id,
            restaurant_id=restaurant_id,
            customer_id=customer_id,
            customer_phone=customer_phone,
            cart_id=f"cart_{call_session_id}",
        )
        cart_id = self.state.cart_id
        assert cart_id is not None
        self.cart_service.create_cart(
            CartContext(
                cart_id=cart_id,
                restaurant_id=restaurant_id,
                customer_id=customer_id,
                call_session_id=call_session_id,
            )
        )

    def respond(self, user_text: str) -> ConversationTurnResult:
        intent = ConversationIntent(self.planner.plan(user_text))
        handlers = {
            ConversationIntent.GREETING: self._handle_greeting,
            ConversationIntent.MENU: self._handle_menu,
            ConversationIntent.ADD_ITEM: self._handle_add_item,
            ConversationIntent.UPDATE_ITEM: self._handle_update_item,
            ConversationIntent.REMOVE_ITEM: self._handle_remove_item,
            ConversationIntent.REVIEW_CART: self._handle_review_cart,
            ConversationIntent.CONFIRM_CHECKOUT: self._handle_confirm_checkout,
            ConversationIntent.ORDER_STATUS: self._handle_order_status,
            ConversationIntent.COMPLAINT: self._handle_complaint,
            ConversationIntent.HANDOFF: self._handle_handoff,
            ConversationIntent.PAYMENT_WEBHOOK: self._handle_payment_webhook,
            ConversationIntent.UNKNOWN: self._handle_unknown,
        }
        result = handlers[intent](user_text)
        self.state = replace(
            self.state,
            last_intent=intent,
            transcript=(
                *self.state.transcript,
                ConversationTurn(speaker="user", text=user_text),
                ConversationTurn(speaker="assistant", text=result.reply_text),
            ),
        )
        return result

    def _ensure_cart(self) -> str:
        assert self.state.cart_id is not None
        try:
            self.cart_service.get_cart(self.state.cart_id)
        except NotFoundError:
            self.cart_service.create_cart(
                CartContext(
                    cart_id=self.state.cart_id,
                    restaurant_id=self.state.restaurant_id,
                    customer_id=self.state.customer_id,
                    call_session_id=self.state.call_session_id,
                )
            )
        return self.state.cart_id

    def _handle_greeting(self, user_text: str) -> ConversationTurnResult:
        del user_text
        return ConversationTurnResult(
            reply_text=(
                "Welcome to Copper Spoon Kitchen. You can ask for the menu, add items, "
                "review your cart, or say checkout when you're ready."
            ),
            topic=ConversationIntent.GREETING.value,
        )

    def _handle_menu(self, user_text: str) -> ConversationTurnResult:
        hits = self.toolset.search_menu(
            SearchMenuInput(
                restaurant_id=self.state.restaurant_id,
                query=user_text,
                limit=5,
            )
        )
        if not hits:
            return ConversationTurnResult(
                reply_text="I could not find a matching item. Try naming the dish or ingredient.",
                topic=ConversationIntent.MENU.value,
            )
        reply = "Here is what I found: " + "; ".join(
            f"{hit.item.name} ({hit.item.base_price}, score {hit.score:.0f})" for hit in hits
        )
        return ConversationTurnResult(
            reply_text=reply,
            topic=ConversationIntent.MENU.value,
            tool_outputs=tuple({"item": hit.item.id.value, "score": hit.score} for hit in hits),
        )

    def _resolve_menu_item(self, user_text: str) -> MenuSearchHit | None:
        query = _extract_item_query(user_text)
        hits = self.toolset.search_menu(
            SearchMenuInput(
                restaurant_id=self.state.restaurant_id,
                query=query or user_text,
                limit=3,
            )
        )
        if not hits:
            return None
        if len(hits) > 1 and hits[0].score - hits[1].score < 8:
            return None
        return hits[0]

    def _handle_add_item(self, user_text: str) -> ConversationTurnResult:
        cart_id = self._ensure_cart()
        search_hit = self._resolve_menu_item(user_text)
        if search_hit is None:
            return ConversationTurnResult(
                reply_text="I could not identify the item you want. Try asking for the menu first.",
                topic=ConversationIntent.ADD_ITEM.value,
            )

        quantity = _extract_quantity(user_text)
        selections = _extract_modifier_selections(search_hit.item, user_text)
        summary = self.cart_service.add_item(
            cart_id,
            self.state.restaurant_id,
            search_hit.item.id.value,
            quantity=quantity,
            modifier_selections=selections,
        )
        return ConversationTurnResult(
            reply_text=f"Added {quantity} x {search_hit.item.name}. {_cart_summary_text(summary)}",
            topic=ConversationIntent.ADD_ITEM.value,
            cart_summary=summary,
        )

    def _handle_update_item(self, user_text: str) -> ConversationTurnResult:
        del user_text
        return ConversationTurnResult(
            reply_text="Tell me which cart item to update and what should change.",
            topic=ConversationIntent.UPDATE_ITEM.value,
        )

    def _handle_remove_item(self, user_text: str) -> ConversationTurnResult:
        if self.state.cart_id is None:
            return ConversationTurnResult(
                reply_text="There is no active cart to remove from yet.",
                topic=ConversationIntent.REMOVE_ITEM.value,
            )
        cart_id = self.state.cart_id
        summary = self.cart_service.get_cart(cart_id)
        matches = [
            line
            for line in summary.lines
            if any(token in user_text.lower() for token in _tokenize(line.menu_item_name))
        ]
        if not matches:
            return ConversationTurnResult(
                reply_text="Tell me which item to remove from the cart.",
                topic=ConversationIntent.REMOVE_ITEM.value,
            )
        updated = self.cart_service.remove_item(
            self.state.cart_id,
            self.state.restaurant_id,
            matches[0].line_id,
        )
        return ConversationTurnResult(
            reply_text=f"Removed {matches[0].menu_item_name}. {_cart_summary_text(updated)}",
            topic=ConversationIntent.REMOVE_ITEM.value,
            cart_summary=updated,
        )

    def _handle_review_cart(self, user_text: str) -> ConversationTurnResult:
        del user_text
        if self.state.cart_id is None:
            return ConversationTurnResult(
                reply_text="Your cart is empty so far. Tell me what you would like to order.",
                topic=ConversationIntent.REVIEW_CART.value,
            )
        cart_id = self.state.cart_id
        summary = self.cart_service.get_cart(cart_id)
        return ConversationTurnResult(
            reply_text=_cart_summary_text(summary),
            topic=ConversationIntent.REVIEW_CART.value,
            cart_summary=summary,
        )

    def _handle_confirm_checkout(self, user_text: str) -> ConversationTurnResult:
        if self.state.cart_id is None:
            return ConversationTurnResult(
                reply_text="I need items in the cart before I can confirm anything.",
                topic=ConversationIntent.CONFIRM_CHECKOUT.value,
            )
        cart_id = self.state.cart_id

        preview = self.toolset.preview_checkout(
            PreviewCheckoutInput(
                cart_id=cart_id,
                restaurant_id=self.state.restaurant_id,
            )
        )
        self.state = replace(self.state, pending_checkout=preview)

        if not preview.ready:
            changes = "; ".join(issue.message for issue in preview.issues)
            return ConversationTurnResult(
                reply_text=f"I found changes before checkout: {changes}",
                topic=ConversationIntent.CONFIRM_CHECKOUT.value,
                cart_summary=self.cart_service.get_cart(cart_id),
            )

        if not _affirmative(user_text):
            return ConversationTurnResult(
                reply_text=(
                    f"Your total is {preview.quote.total}. Say yes to confirm the cart "
                    "and I will send the payment link."
                ),
                topic=ConversationIntent.CONFIRM_CHECKOUT.value,
                cart_summary=self.cart_service.get_cart(cart_id),
            )

        confirmed = self.toolset.confirm_cart(
            ConfirmCartInput(
                cart_id=cart_id,
                restaurant_id=self.state.restaurant_id,
                customer_id=self.state.customer_id,
                call_session_id=self.state.call_session_id,
            )
        )
        checkout = self.toolset.create_checkout_session(
            CreateCheckoutSessionInput(
                order_id=confirmed.summary.order_id,
                customer_phone=self.state.customer_phone,
            )
        )
        self.state = replace(
            self.state,
            order_id=confirmed.summary.order_id,
            last_checkout=checkout,
            pending_checkout=None,
        )
        return ConversationTurnResult(
            reply_text=(
                f"Your order #{confirmed.summary.display_number} is ready. "
                f"Please pay here: {checkout.checkout_url}"
            ),
            topic=ConversationIntent.CONFIRM_CHECKOUT.value,
            order_summary=confirmed.summary,
            checkout_session=checkout,
        )

    def _handle_order_status(self, user_text: str) -> ConversationTurnResult:
        del user_text
        if self.state.order_id is None:
            return ConversationTurnResult(
                reply_text=(
                    "I do not have an order on file yet. Tell me your order number if you have one."
                ),
                topic=ConversationIntent.ORDER_STATUS.value,
            )
        order = self.toolset.lookup_order(LookupOrderInput(order_id=self.state.order_id))
        return ConversationTurnResult(
            reply_text=f"Order #{order.display_number} is currently {order.status}.",
            topic=ConversationIntent.ORDER_STATUS.value,
            order_summary=order,
        )

    def _handle_complaint(self, user_text: str) -> ConversationTurnResult:
        category = "OTHER"
        lowered = user_text.lower()
        if "allergy" in lowered:
            category = "ALLERGY_CONCERN"
        elif "missing" in lowered:
            category = "MISSING_ITEM"
        elif "wrong" in lowered:
            category = "WRONG_ITEM"
        elif "late" in lowered:
            category = "LATE_ORDER"
        complaint = self.toolset.create_complaint(
            CreateComplaintInput(
                restaurant_id=self.state.restaurant_id,
                category=category,
                notes=user_text,
                order_id=self.state.order_id,
                customer_id=self.state.customer_id,
            )
        )
        handoff = self.toolset.create_handoff(
            CreateHandoffInput(
                restaurant_id=self.state.restaurant_id,
                reason=f"Complaint escalation: {user_text}",
                order_id=self.state.order_id,
                customer_id=self.state.customer_id,
                notes=user_text,
            )
        )
        return ConversationTurnResult(
            reply_text="I captured the complaint and prepared a human handoff.",
            topic=ConversationIntent.COMPLAINT.value,
            complaint_summary=complaint,
            handoff_summary=handoff,
        )

    def _handle_handoff(self, user_text: str) -> ConversationTurnResult:
        handoff = self.toolset.create_handoff(
            CreateHandoffInput(
                restaurant_id=self.state.restaurant_id,
                reason=user_text,
                order_id=self.state.order_id,
                customer_id=self.state.customer_id,
                notes=user_text,
            )
        )
        return ConversationTurnResult(
            reply_text="I have prepared a handoff to a person on the team.",
            topic=ConversationIntent.HANDOFF.value,
            handoff_summary=handoff,
        )

    def _handle_payment_webhook(self, user_text: str) -> ConversationTurnResult:
        del user_text
        return ConversationTurnResult(
            reply_text="Payment webhooks are handled by the payment service, not by chat.",
            topic=ConversationIntent.PAYMENT_WEBHOOK.value,
        )

    def _handle_unknown(self, user_text: str) -> ConversationTurnResult:
        del user_text
        return ConversationTurnResult(
            reply_text=(
                "I can help with the menu, cart, checkout, order status, complaints, or a handoff."
            ),
            topic=ConversationIntent.UNKNOWN.value,
        )
