"""Menu catalog lookup, search, and price revalidation services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.models import (
    MenuSearchHit,
    PriceRevalidationIssue,
    PriceRevalidationResult,
)
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.domain.cart import Cart, CartLineDraftSnapshot
from restaurant_voice_agent.domain.menu import MenuItem, ModifierSelectionRequest
from restaurant_voice_agent.domain.pricing import calculate_cart_pricing

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(value: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(value.lower()))


@dataclass(frozen=True)
class SearchConstraints:
    """Filters to apply to menu search."""

    include_unavailable: bool = False
    limit: int = 5


class MenuCatalogService:
    """Read-only menu lookup and search."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    def get_menu_item(self, restaurant_id: str, menu_item_id: str) -> MenuItem:
        with self.uow_factory() as uow:
            record = uow.menu.get_menu_item(menu_item_id)
            if record is None:
                raise NotFoundError(f"Menu item {menu_item_id!r} was not found")
            if not self._belongs_to_restaurant(uow, restaurant_id, menu_item_id):
                raise NotFoundError(f"Menu item {menu_item_id!r} was not found")
            return record

    def list_menu_items(
        self, restaurant_id: str, *, include_unavailable: bool = False
    ) -> list[MenuItem]:
        with self.uow_factory() as uow:
            items = uow.menu.list_menu_items(restaurant_id)
            if include_unavailable:
                return items
            return [item for item in items if item.available]

    def search(
        self,
        restaurant_id: str,
        query: str,
        *,
        include_unavailable: bool = False,
        limit: int = 5,
    ) -> list[MenuSearchHit]:
        query_tokens = _tokenize(query)
        query_lower = query.lower().strip()
        hits: list[MenuSearchHit] = []

        for item in self.list_menu_items(restaurant_id, include_unavailable=include_unavailable):
            score = 0.0
            reasons: list[str] = []
            item_tokens = _tokenize(item.name)
            modifier_tokens = _tokenize(" ".join(group.name for group in item.modifier_groups))
            allergen_tokens = _tokenize(" ".join(item.allergens))
            searchable_tokens = item_tokens | modifier_tokens | allergen_tokens

            if item.id.value == query_lower:
                score += 100.0
                reasons.append("exact id match")
            if item.name.lower() == query_lower:
                score += 90.0
                reasons.append("exact name match")
            if query_lower and query_lower in item.name.lower():
                score += 60.0
                reasons.append("name contains query")

            overlap = len(query_tokens & searchable_tokens)
            if overlap:
                score += float(overlap * 12)
                reasons.append(f"{overlap} token match(es)")

            if item.available:
                score += 1.0
                reasons.append("available")

            if score > 0:
                hits.append(MenuSearchHit(item=item, score=score, reasons=tuple(reasons)))

        hits.sort(key=lambda hit: (-hit.score, hit.item.name.lower(), hit.item.id.value))
        return hits[:limit]

    def _belongs_to_restaurant(
        self, uow: UnitOfWork, restaurant_id: str, menu_item_id: str
    ) -> bool:
        for item in uow.menu.list_menu_items(restaurant_id):
            if item.id.value == menu_item_id:
                return True
        return False


class PriceRevalidationService:
    """Recompute a cart against live menu data before checkout."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    def revalidate_cart(self, restaurant_id: str, cart: Cart) -> PriceRevalidationResult:
        live_lines: list[CartLineDraftSnapshot] = []
        issues: list[PriceRevalidationIssue] = []

        with self.uow_factory() as uow:
            for line in cart.lines:
                live_item = uow.menu.get_menu_item(line.menu_item_id.value)
                if live_item is None or not live_item.available:
                    issues.append(
                        PriceRevalidationIssue(
                            line_id=line.line_id.value,
                            message=f"{line.menu_item_name} is no longer available.",
                            captured_total=line.line_total,
                            live_total=None,
                            kind="unavailable",
                        )
                    )
                    continue

                live_requests = tuple(
                    ModifierSelectionRequest(
                        group_id=modifier.group_id, modifier_id=modifier.modifier_id
                    )
                    for modifier in line.modifiers
                )
                live_modifiers = live_item.validate_modifier_selections(live_requests)
                live_line = CartLineDraftSnapshot(
                    line_id=line.line_id,
                    menu_item_id=live_item.id,
                    menu_item_name=live_item.name,
                    unit_price=live_item.base_price,
                    quantity=line.quantity,
                    modifiers=live_modifiers,
                )
                live_lines.append(live_line)

                if live_line.line_total != line.line_total or live_line != line:
                    issues.append(
                        PriceRevalidationIssue(
                            line_id=line.line_id.value,
                            message=(
                                f"Price changed for {line.menu_item_name}: "
                                f"{line.line_total} -> {live_line.line_total}"
                            ),
                            captured_total=line.line_total,
                            live_total=live_line.line_total,
                            kind="price_changed",
                        )
                    )

        live_cart = Cart(lines=tuple(live_lines))
        quote = calculate_cart_pricing(live_cart)
        return PriceRevalidationResult(cart=live_cart, quote=quote, issues=tuple(issues))
