"""Tests for the text conversation workflow."""

from __future__ import annotations

from decimal import Decimal

from restaurant_voice_agent.application.cart import CartService
from restaurant_voice_agent.application.catalog import MenuCatalogService, PriceRevalidationService
from restaurant_voice_agent.application.complaints import ComplaintService
from restaurant_voice_agent.application.handoffs import HandoffService
from restaurant_voice_agent.application.orders import OrderService
from restaurant_voice_agent.application.payments import PaymentService
from restaurant_voice_agent.application.tools import build_toolset
from restaurant_voice_agent.application.workflow import ConversationWorkflow

from .helpers import seed_restaurant_catalog


def test_conversation_workflow_supports_menu_cart_and_checkout(uow_factory, session) -> None:
    restaurant_id, burger, _ = seed_restaurant_catalog(session)
    cart_service = CartService(uow_factory)
    menu_service = MenuCatalogService(uow_factory)
    order_service = OrderService(
        uow_factory,
        cart_service=cart_service,
        price_revalidation_service=PriceRevalidationService(uow_factory),
    )
    payment_service = PaymentService(uow_factory)
    toolset = build_toolset(
        menu_service=menu_service,
        cart_service=cart_service,
        order_service=order_service,
        payment_service=payment_service,
        complaint_service=ComplaintService(uow_factory),
        handoff_service=HandoffService(uow_factory),
    )

    workflow = ConversationWorkflow(
        toolset=toolset,
        cart_service=cart_service,
        call_session_id="call_123",
        restaurant_id=restaurant_id,
    )

    menu_reply = workflow.respond("What do you have?")
    assert menu_reply.topic == "menu"
    assert "Classic Burger" in menu_reply.reply_text

    add_reply = workflow.respond("add a classic burger with cheese")
    assert add_reply.topic == "add_item"
    assert add_reply.cart_summary is not None
    assert add_reply.cart_summary.line_count == 1
    assert add_reply.cart_summary.quote.total.amount == Decimal("11.00")

    review_reply = workflow.respond("review cart")
    assert review_reply.topic == "review_cart"
    assert review_reply.cart_summary is not None
    assert "Classic Burger" in review_reply.reply_text

    confirm_reply = workflow.respond("yes checkout")
    assert confirm_reply.topic == "confirm_checkout"
    assert confirm_reply.order_summary is not None
    assert confirm_reply.checkout_session is not None
    assert confirm_reply.checkout_session.checkout_url.startswith("https://checkout.local/")
    assert confirm_reply.order_summary.status == "AWAITING_PAYMENT"
    assert workflow.state.order_id == confirm_reply.order_summary.order_id

    status_reply = workflow.respond("order status")
    assert status_reply.topic == "order_status"
    assert "AWAITING_PAYMENT" in status_reply.reply_text

    assert burger.name in confirm_reply.order_summary.lines[0].menu_item_name
