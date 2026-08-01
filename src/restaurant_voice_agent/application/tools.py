"""Typed tools exposed to the conversation engine."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Callable, Generic, Mapping, TypeVar, cast

from restaurant_voice_agent.application.cart import CartService
from restaurant_voice_agent.application.catalog import MenuCatalogService
from restaurant_voice_agent.application.complaints import ComplaintRequest, ComplaintService
from restaurant_voice_agent.application.errors import ToolValidationError
from restaurant_voice_agent.application.handoffs import HandoffRequest, HandoffService
from restaurant_voice_agent.application.models import (
    CartSummary,
    CheckoutPreview,
    CheckoutSession,
    ComplaintSummary,
    HandoffSummary,
    MenuSearchHit,
    OrderSummary,
)
from restaurant_voice_agent.application.orders import ConfirmedCartResult, OrderService
from restaurant_voice_agent.application.payments import PaymentService, PaymentWebhookResult
from restaurant_voice_agent.domain.cart import CartLineId
from restaurant_voice_agent.domain.enums import ComplaintCategory
from restaurant_voice_agent.domain.identifiers import ModifierGroupId, ModifierId
from restaurant_voice_agent.domain.menu import ModifierSelectionRequest

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class ModifierSelectionInput:
    """Tool input for selecting a modifier."""

    group_id: str
    modifier_id: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ModifierSelectionInput":
        return cls(group_id=str(payload["group_id"]), modifier_id=str(payload["modifier_id"]))

    def to_domain(self) -> ModifierSelectionRequest:
        return ModifierSelectionRequest(
            group_id=ModifierGroupId(self.group_id),
            modifier_id=ModifierId(self.modifier_id),
        )


@dataclass(frozen=True)
class SearchMenuInput:
    """Tool input for menu search."""

    restaurant_id: str
    query: str
    limit: int = 5
    include_unavailable: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SearchMenuInput":
        return cls(
            restaurant_id=str(payload["restaurant_id"]),
            query=str(payload["query"]),
            limit=int(payload.get("limit", 5)),
            include_unavailable=bool(payload.get("include_unavailable", False)),
        )


@dataclass(frozen=True)
class AddCartItemInput:
    """Tool input for adding an item to a cart."""

    cart_id: str
    restaurant_id: str
    menu_item_id: str
    quantity: int = 1
    modifier_selections: tuple[ModifierSelectionInput, ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AddCartItemInput":
        selections_payload = payload.get("modifier_selections", ())
        selections = tuple(ModifierSelectionInput.from_mapping(item) for item in selections_payload)
        return cls(
            cart_id=str(payload["cart_id"]),
            restaurant_id=str(payload["restaurant_id"]),
            menu_item_id=str(payload["menu_item_id"]),
            quantity=int(payload.get("quantity", 1)),
            modifier_selections=selections,
        )

    def to_domain(self) -> tuple[ModifierSelectionRequest, ...]:
        return tuple(selection.to_domain() for selection in self.modifier_selections)


@dataclass(frozen=True)
class UpdateCartItemInput:
    """Tool input for updating an existing cart line."""

    cart_id: str
    restaurant_id: str
    line_id: str
    quantity: int | None = None
    menu_item_id: str | None = None
    modifier_selections: tuple[ModifierSelectionInput, ...] | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "UpdateCartItemInput":
        selections_payload = payload.get("modifier_selections")
        selections = None
        if selections_payload is not None:
            selections = tuple(
                ModifierSelectionInput.from_mapping(item) for item in selections_payload
            )
        return cls(
            cart_id=str(payload["cart_id"]),
            restaurant_id=str(payload["restaurant_id"]),
            line_id=str(payload["line_id"]),
            quantity=int(payload["quantity"]) if payload.get("quantity") is not None else None,
            menu_item_id=str(payload["menu_item_id"]) if payload.get("menu_item_id") else None,
            modifier_selections=selections,
        )

    def to_domain(self) -> tuple[ModifierSelectionRequest, ...] | None:
        if self.modifier_selections is None:
            return None
        return tuple(selection.to_domain() for selection in self.modifier_selections)


@dataclass(frozen=True)
class RemoveCartItemInput:
    """Tool input for removing a cart line."""

    cart_id: str
    restaurant_id: str
    line_id: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RemoveCartItemInput":
        return cls(
            cart_id=str(payload["cart_id"]),
            restaurant_id=str(payload["restaurant_id"]),
            line_id=str(payload["line_id"]),
        )


@dataclass(frozen=True)
class PreviewCheckoutInput:
    """Tool input for revalidating a cart before checkout."""

    cart_id: str
    restaurant_id: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PreviewCheckoutInput":
        return cls(cart_id=str(payload["cart_id"]), restaurant_id=str(payload["restaurant_id"]))


@dataclass(frozen=True)
class LookupOrderInput:
    """Tool input for looking up an order."""

    order_id: str | None = None
    display_number: int | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LookupOrderInput":
        order_id = str(payload["order_id"]) if payload.get("order_id") else None
        display_number = int(payload["display_number"]) if payload.get("display_number") else None
        return cls(order_id=order_id, display_number=display_number)


@dataclass(frozen=True)
class ConfirmCartInput:
    """Tool input for creating the permanent order snapshot."""

    cart_id: str
    restaurant_id: str
    customer_id: str | None = None
    call_session_id: str | None = None
    idempotency_key: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ConfirmCartInput":
        customer_id = str(payload["customer_id"]) if payload.get("customer_id") else None
        call_session_id = (
            str(payload["call_session_id"]) if payload.get("call_session_id") else None
        )
        idempotency_key = (
            str(payload["idempotency_key"]) if payload.get("idempotency_key") else None
        )
        return cls(
            cart_id=str(payload["cart_id"]),
            restaurant_id=str(payload["restaurant_id"]),
            customer_id=customer_id,
            call_session_id=call_session_id,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True)
class CreateCheckoutSessionInput:
    """Tool input for generating a payment checkout link."""

    order_id: str
    customer_phone: str | None = None
    send_sms: bool = True

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CreateCheckoutSessionInput":
        customer_phone = str(payload["customer_phone"]) if payload.get("customer_phone") else None
        return cls(
            order_id=str(payload["order_id"]),
            customer_phone=customer_phone,
            send_sms=bool(payload.get("send_sms", True)),
        )


@dataclass(frozen=True)
class PaymentWebhookInput:
    """Tool input for processing a payment provider webhook."""

    payload: bytes | str | Mapping[str, Any]
    signature: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PaymentWebhookInput":
        return cls(payload=payload["payload"], signature=str(payload["signature"]))


@dataclass(frozen=True)
class CreateComplaintInput:
    """Tool input for opening a complaint."""

    restaurant_id: str
    category: str
    notes: str
    order_id: str | None = None
    customer_id: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CreateComplaintInput":
        return cls(
            restaurant_id=str(payload["restaurant_id"]),
            category=str(payload["category"]),
            notes=str(payload["notes"]),
            order_id=str(payload["order_id"]) if payload.get("order_id") else None,
            customer_id=str(payload["customer_id"]) if payload.get("customer_id") else None,
        )

    def to_domain(self) -> ComplaintRequest:
        return ComplaintRequest(
            restaurant_id=self.restaurant_id,
            category=ComplaintCategory(self.category),
            notes=self.notes,
            order_id=self.order_id,
            customer_id=self.customer_id,
        )


@dataclass(frozen=True)
class CreateHandoffInput:
    """Tool input for creating a human handoff."""

    restaurant_id: str
    reason: str
    destination: str | None = None
    order_id: str | None = None
    customer_id: str | None = None
    notes: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CreateHandoffInput":
        return cls(
            restaurant_id=str(payload["restaurant_id"]),
            reason=str(payload["reason"]),
            destination=str(payload["destination"]) if payload.get("destination") else None,
            order_id=str(payload["order_id"]) if payload.get("order_id") else None,
            customer_id=str(payload["customer_id"]) if payload.get("customer_id") else None,
            notes=str(payload["notes"]) if payload.get("notes") else None,
        )

    def to_domain(self) -> HandoffRequest:
        return HandoffRequest(
            restaurant_id=self.restaurant_id,
            reason=self.reason,
            destination=self.destination,
            order_id=self.order_id,
            customer_id=self.customer_id,
            notes=self.notes,
        )


class TypedTool(Generic[InputT, OutputT]):
    """A strongly typed tool wrapper with input validation."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_type: type[InputT],
        handler: Callable[[InputT], OutputT],
    ) -> None:
        self.name = name
        self.description = description
        self.input_type = input_type
        self.handler = handler

    def parse(self, value: InputT | Mapping[str, Any]) -> InputT:
        input_type = cast(type[Any], self.input_type)
        if isinstance(value, input_type):
            return cast(InputT, value)
        if isinstance(value, Mapping):
            payload = cast(Mapping[str, Any], value)
            try:
                from_mapping = cast(
                    Callable[[Mapping[str, Any]], InputT],
                    input_type.from_mapping,
                )
            except AttributeError:
                from_mapping = None
            if callable(from_mapping):
                return from_mapping(payload)
            field_names = {field.name for field in fields(cast(Any, input_type))}
            unknown = set(payload) - field_names
            if unknown:
                raise ToolValidationError(
                    f"Tool {self.name} received unknown fields: {sorted(unknown)}"
                )
            return cast(InputT, input_type(**dict(payload)))
        raise ToolValidationError(f"Tool {self.name} requires {self.input_type.__name__} input")

    def __call__(self, value: InputT | Mapping[str, Any]) -> OutputT:
        return self.handler(self.parse(value))


@dataclass(frozen=True)
class Toolset:
    """A stable collection of customer-facing tools."""

    search_menu: TypedTool[SearchMenuInput, list[MenuSearchHit]]
    add_cart_item: TypedTool[AddCartItemInput, CartSummary]
    update_cart_item: TypedTool[UpdateCartItemInput, CartSummary]
    remove_cart_item: TypedTool[RemoveCartItemInput, CartSummary]
    preview_checkout: TypedTool[PreviewCheckoutInput, CheckoutPreview]
    confirm_cart: TypedTool[ConfirmCartInput, ConfirmedCartResult]
    create_checkout_session: TypedTool[CreateCheckoutSessionInput, CheckoutSession]
    process_payment_webhook: TypedTool[PaymentWebhookInput, PaymentWebhookResult]
    lookup_order: TypedTool[LookupOrderInput, OrderSummary]
    create_complaint: TypedTool[CreateComplaintInput, ComplaintSummary]
    create_handoff: TypedTool[CreateHandoffInput, HandoffSummary]


def build_toolset(
    *,
    menu_service: MenuCatalogService,
    cart_service: CartService,
    order_service: OrderService,
    payment_service: PaymentService,
    complaint_service: ComplaintService,
    handoff_service: HandoffService,
) -> Toolset:
    """Build the canonical tool bundle for a call session."""

    def _search_menu(payload: SearchMenuInput) -> list[MenuSearchHit]:
        return menu_service.search(
            payload.restaurant_id,
            payload.query,
            include_unavailable=payload.include_unavailable,
            limit=payload.limit,
        )

    def _add_cart_item(payload: AddCartItemInput) -> CartSummary:
        return cart_service.add_item(
            payload.cart_id,
            payload.restaurant_id,
            payload.menu_item_id,
            quantity=payload.quantity,
            modifier_selections=payload.to_domain(),
        )

    def _update_cart_item(payload: UpdateCartItemInput) -> CartSummary:
        return cart_service.update_item(
            payload.cart_id,
            payload.restaurant_id,
            CartLineId(payload.line_id),
            quantity=payload.quantity,
            menu_item_id=payload.menu_item_id,
            modifier_selections=payload.to_domain(),
        )

    def _remove_cart_item(payload: RemoveCartItemInput) -> CartSummary:
        return cart_service.remove_item(
            payload.cart_id,
            payload.restaurant_id,
            CartLineId(payload.line_id),
        )

    def _preview_checkout(payload: PreviewCheckoutInput) -> CheckoutPreview:
        return order_service.preview_checkout(payload.cart_id, payload.restaurant_id)

    def _confirm_cart(payload: ConfirmCartInput) -> ConfirmedCartResult:
        return order_service.confirm_cart(
            cart_id=payload.cart_id,
            restaurant_id=payload.restaurant_id,
            customer_id=payload.customer_id,
            call_session_id=payload.call_session_id,
            idempotency_key=payload.idempotency_key,
        )

    def _create_checkout(payload: CreateCheckoutSessionInput) -> CheckoutSession:
        return payment_service.create_checkout_session(
            order_id=payload.order_id,
            customer_phone=payload.customer_phone,
            send_sms=payload.send_sms,
        )

    def _process_payment_webhook(payload: PaymentWebhookInput) -> PaymentWebhookResult:
        return payment_service.handle_webhook(payload=payload.payload, signature=payload.signature)

    def _lookup_order(payload: LookupOrderInput) -> OrderSummary:
        if payload.order_id is not None:
            return order_service.get_order(payload.order_id)
        if payload.display_number is not None:
            return order_service.get_order_by_display_number(payload.display_number)
        raise ToolValidationError("Order lookup requires an order_id or display_number")

    def _create_complaint(payload: CreateComplaintInput) -> ComplaintSummary:
        return complaint_service.create_complaint(payload.to_domain())

    def _create_handoff(payload: CreateHandoffInput) -> HandoffSummary:
        return handoff_service.create_handoff(payload.to_domain())

    return Toolset(
        search_menu=TypedTool(
            name="search_menu",
            description="Search menu items with exact, keyword, and availability ranking.",
            input_type=SearchMenuInput,
            handler=_search_menu,
        ),
        add_cart_item=TypedTool(
            name="add_cart_item",
            description="Add an item to the live cart.",
            input_type=AddCartItemInput,
            handler=_add_cart_item,
        ),
        update_cart_item=TypedTool(
            name="update_cart_item",
            description="Update an existing live cart line.",
            input_type=UpdateCartItemInput,
            handler=_update_cart_item,
        ),
        remove_cart_item=TypedTool(
            name="remove_cart_item",
            description="Remove a cart line.",
            input_type=RemoveCartItemInput,
            handler=_remove_cart_item,
        ),
        preview_checkout=TypedTool(
            name="preview_checkout",
            description="Revalidate a cart before checkout.",
            input_type=PreviewCheckoutInput,
            handler=_preview_checkout,
        ),
        confirm_cart=TypedTool(
            name="confirm_cart",
            description="Turn a validated cart into a permanent order snapshot.",
            input_type=ConfirmCartInput,
            handler=_confirm_cart,
        ),
        create_checkout_session=TypedTool(
            name="create_checkout_session",
            description="Create a payment checkout session from a stored order total.",
            input_type=CreateCheckoutSessionInput,
            handler=_create_checkout,
        ),
        process_payment_webhook=TypedTool(
            name="process_payment_webhook",
            description="Verify and process a payment provider webhook.",
            input_type=PaymentWebhookInput,
            handler=_process_payment_webhook,
        ),
        lookup_order=TypedTool(
            name="lookup_order",
            description="Look up a stored order by order id or display number.",
            input_type=LookupOrderInput,
            handler=_lookup_order,
        ),
        create_complaint=TypedTool(
            name="create_complaint",
            description="Open a customer complaint.",
            input_type=CreateComplaintInput,
            handler=_create_complaint,
        ),
        create_handoff=TypedTool(
            name="create_handoff",
            description="Create a human handoff summary.",
            input_type=CreateHandoffInput,
            handler=_create_handoff,
        ),
    )
