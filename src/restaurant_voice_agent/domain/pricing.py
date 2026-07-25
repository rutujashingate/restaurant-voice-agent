"""Deterministic cart pricing."""

from __future__ import annotations

from dataclasses import dataclass

from .cart import Cart
from .money import Money


@dataclass(frozen=True)
class CartPricingBreakdown:
    """Deterministic pricing summary for a cart."""

    item_subtotal: Money
    modifier_subtotal: Money
    subtotal: Money
    total: Money


def calculate_cart_pricing(cart: Cart) -> CartPricingBreakdown:
    item_subtotal = Money.zero()
    modifier_subtotal = Money.zero()

    for line in cart.lines:
        item_subtotal = item_subtotal + line.item_subtotal
        modifier_subtotal = modifier_subtotal + line.modifier_subtotal

    subtotal = item_subtotal + modifier_subtotal
    return CartPricingBreakdown(
        item_subtotal=item_subtotal,
        modifier_subtotal=modifier_subtotal,
        subtotal=subtotal,
        total=subtotal,
    )
