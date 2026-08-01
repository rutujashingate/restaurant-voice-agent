"""Cart lifecycle services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from restaurant_voice_agent.application.catalog import MenuCatalogService
from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.models import CartSummary
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.domain.cart import Cart
from restaurant_voice_agent.domain.identifiers import CartLineId
from restaurant_voice_agent.domain.menu import MenuItem, ModifierSelectionRequest
from restaurant_voice_agent.domain.pricing import calculate_cart_pricing
from restaurant_voice_agent.persistence.models import CartRecord


@dataclass(frozen=True)
class CartContext:
    """Stored cart ownership metadata."""

    cart_id: str
    restaurant_id: str
    customer_id: str | None = None
    call_session_id: str | None = None
    source: str = "voice"


class CartService:
    """Persist and mutate draft carts."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        catalog_service: MenuCatalogService | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.catalog_service = catalog_service or MenuCatalogService(uow_factory)

    def create_cart(self, context: CartContext) -> CartSummary:
        with self.uow_factory() as uow:
            if uow.carts.get(context.cart_id) is None:
                uow.carts.upsert(
                    CartRecord(
                        id=context.cart_id,
                        restaurant_id=context.restaurant_id,
                        customer_id=context.customer_id,
                        call_session_id=context.call_session_id,
                        status="OPEN",
                        source=context.source,
                    )
                )
            return self._build_summary(uow, context.cart_id)

    def get_cart(self, cart_id: str) -> CartSummary:
        with self.uow_factory() as uow:
            return self._build_summary(uow, cart_id)

    def add_item(
        self,
        cart_id: str,
        restaurant_id: str,
        menu_item_id: str,
        *,
        quantity: int = 1,
        modifier_selections: Sequence[ModifierSelectionRequest] = (),
    ) -> CartSummary:
        with self.uow_factory() as uow:
            cart = self._load_cart(uow, cart_id)
            menu_item = self._load_menu_item(restaurant_id, menu_item_id)
            updated = cart.add_item(
                menu_item,
                quantity=quantity,
                modifier_selections=modifier_selections,
            )
            self._save_cart(uow, cart_id, updated, restaurant_id)
            return self._build_summary(uow, cart_id)

    def update_item(
        self,
        cart_id: str,
        restaurant_id: str,
        line_id: CartLineId,
        *,
        quantity: int | None = None,
        menu_item_id: str | None = None,
        modifier_selections: Sequence[ModifierSelectionRequest] | None = None,
    ) -> CartSummary:
        with self.uow_factory() as uow:
            cart = self._load_cart(uow, cart_id)
            menu_item = (
                self._load_menu_item(restaurant_id, menu_item_id)
                if menu_item_id is not None
                else None
            )
            updated = cart.update_item(
                line_id,
                quantity=quantity,
                menu_item=menu_item,
                modifier_selections=modifier_selections,
            )
            self._save_cart(uow, cart_id, updated, restaurant_id)
            return self._build_summary(uow, cart_id)

    def remove_item(self, cart_id: str, restaurant_id: str, line_id: CartLineId) -> CartSummary:
        with self.uow_factory() as uow:
            cart = self._load_cart(uow, cart_id)
            updated = cart.remove_item(line_id)
            self._save_cart(uow, cart_id, updated, restaurant_id)
            return self._build_summary(uow, cart_id)

    def clear_cart(self, cart_id: str, restaurant_id: str) -> CartSummary:
        with self.uow_factory() as uow:
            cart = Cart.empty()
            self._save_cart(uow, cart_id, cart, restaurant_id)
            return self._build_summary(uow, cart_id)

    def load_domain_cart(self, cart_id: str) -> Cart:
        with self.uow_factory() as uow:
            if uow.carts.get(cart_id) is None:
                raise NotFoundError(f"Cart {cart_id!r} was not found")
            return Cart(lines=tuple(uow.carts.list_lines(cart_id)))

    def quote_cart(self, cart_id: str) -> CartSummary:
        with self.uow_factory() as uow:
            return self._build_summary(uow, cart_id)

    def _load_cart(self, uow: UnitOfWork, cart_id: str) -> Cart:
        lines = tuple(uow.carts.list_lines(cart_id))
        if not lines and uow.carts.get(cart_id) is None:
            raise NotFoundError(f"Cart {cart_id!r} was not found")
        return Cart(lines=lines)

    def _load_menu_item(self, restaurant_id: str, menu_item_id: str) -> MenuItem:
        return self.catalog_service.get_menu_item(restaurant_id, menu_item_id)

    def _save_cart(self, uow: UnitOfWork, cart_id: str, cart: Cart, restaurant_id: str) -> None:
        stored = uow.carts.get(cart_id)
        if stored is None:
            uow.carts.upsert(
                CartRecord(
                    id=cart_id,
                    restaurant_id=restaurant_id,
                    status="OPEN",
                    source="voice",
                )
            )
        uow.carts.delete_lines(cart_id)
        for line in cart.lines:
            uow.carts.save_line(cart_id, line)

    def _build_summary(self, uow: UnitOfWork, cart_id: str) -> CartSummary:
        record = uow.carts.get(cart_id)
        if record is None:
            raise NotFoundError(f"Cart {cart_id!r} was not found")
        lines = tuple(uow.carts.list_lines(cart_id))
        quote = calculate_cart_pricing(Cart(lines=lines))
        return CartSummary(cart_id=cart_id, lines=lines, quote=quote)
