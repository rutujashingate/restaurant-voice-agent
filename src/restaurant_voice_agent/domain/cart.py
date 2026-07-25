"""Draft cart domain model with deterministic limits and snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from .errors import CartError, CartLimitError
from .identifiers import CartLineId, MenuItemId, ModifierGroupId, ModifierId
from .menu import CapturedModifierSnapshot, MenuItem, ModifierSelectionRequest
from .money import Money

MIN_QUANTITY = 1
MAX_LINE_QUANTITY = 10
MAX_CART_LINE_COUNT = 12
MAX_CART_TOTAL_UNITS = 30


def _line_signature(
    menu_item_id: MenuItemId, modifiers: Sequence[CapturedModifierSnapshot]
) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    modifier_key = tuple(
        sorted(
            ((modifier.group_id.value, modifier.modifier_id.value) for modifier in modifiers),
            key=lambda item: item,
        )
    )
    return (menu_item_id.value, modifier_key)


def _modifier_subtotal_for_quantity(
    modifiers: Sequence[CapturedModifierSnapshot], quantity: int
) -> Money:
    if not modifiers:
        return Money.zero()
    per_unit = Money.zero(currency=modifiers[0].price_delta.currency)
    for modifier in modifiers:
        per_unit = per_unit + modifier.price_delta
    return per_unit * quantity


def _validate_unique_modifiers(modifiers: Sequence[CapturedModifierSnapshot]) -> None:
    keys: list[tuple[ModifierGroupId, ModifierId]] = [
        (modifier.group_id, modifier.modifier_id) for modifier in modifiers
    ]
    if len(keys) != len(set(keys)):
        raise CartError("Cart lines cannot contain duplicate modifiers")


def _validate_line_quantity(quantity: int) -> None:
    if not isinstance(quantity, int):
        raise CartLimitError("Cart quantities must be integers")
    if quantity < MIN_QUANTITY:
        raise CartLimitError("Cart quantities must be at least one")
    if quantity > MAX_LINE_QUANTITY:
        raise CartLimitError("Cart line quantities cannot exceed the configured maximum")


def _validate_money_currency(value: Money) -> None:
    if value.currency != "USD":
        raise CartError("Cart snapshots must use USD amounts")


def _build_captured_line(
    line_id: CartLineId,
    menu_item: MenuItem,
    quantity: int,
    modifiers: Sequence[CapturedModifierSnapshot],
) -> "CartLineDraftSnapshot":
    return CartLineDraftSnapshot(
        line_id=line_id,
        menu_item_id=menu_item.id,
        menu_item_name=menu_item.name,
        unit_price=menu_item.base_price,
        quantity=quantity,
        modifiers=tuple(modifiers),
    )


def _merge_or_replace_lines(
    lines: Sequence["CartLineDraftSnapshot"], candidate: "CartLineDraftSnapshot", index: int
) -> Tuple["CartLineDraftSnapshot", ...]:
    replacement: list[CartLineDraftSnapshot] = list(lines)
    matching_index: Optional[int] = None
    for other_index, other_line in enumerate(replacement):
        if other_index == index:
            continue
        if other_line.signature == candidate.signature:
            matching_index = other_index
            break

    if matching_index is not None:
        other_line = replacement[matching_index]
        merged_quantity = candidate.quantity + other_line.quantity
        if merged_quantity > MAX_LINE_QUANTITY:
            raise CartLimitError("Merged cart line quantity exceeds the maximum allowed")
        merged_line = CartLineDraftSnapshot(
            line_id=candidate.line_id,
            menu_item_id=candidate.menu_item_id,
            menu_item_name=candidate.menu_item_name,
            unit_price=candidate.unit_price,
            quantity=merged_quantity,
            modifiers=candidate.modifiers,
        )
        replacement[index] = merged_line
        del replacement[matching_index]
        return tuple(replacement)

    replacement[index] = candidate
    return tuple(replacement)


class _LineSnapshotMixin(object):
    line_id: CartLineId
    menu_item_id: MenuItemId
    menu_item_name: str
    unit_price: Money
    quantity: int
    modifiers: Tuple[CapturedModifierSnapshot, ...]

    @property
    def signature(self) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        return _line_signature(self.menu_item_id, self.modifiers)

    @property
    def item_subtotal(self) -> Money:
        return self.unit_price * self.quantity

    @property
    def modifier_subtotal(self) -> Money:
        return _modifier_subtotal_for_quantity(self.modifiers, self.quantity)

    @property
    def line_total(self) -> Money:
        return self.item_subtotal + self.modifier_subtotal


@dataclass(frozen=True)
class CartLineDraftSnapshot(_LineSnapshotMixin):
    """Temporary cart-line snapshot."""

    line_id: CartLineId
    menu_item_id: MenuItemId
    menu_item_name: str
    unit_price: Money
    quantity: int
    modifiers: Tuple[CapturedModifierSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not self.menu_item_name.strip():
            raise CartError("Cart line item names cannot be empty")
        if self.unit_price.amount < 0:
            raise CartError("Cart line prices cannot be negative")
        _validate_money_currency(self.unit_price)
        _validate_line_quantity(self.quantity)
        _validate_unique_modifiers(self.modifiers)
        for modifier in self.modifiers:
            if modifier.price_delta.currency != self.unit_price.currency:
                raise CartError("Cart line modifiers must use the same currency as the item")

    def to_submitted_snapshot(self) -> "SubmittedOrderLineSnapshot":
        """Convert a draft snapshot into a permanent submitted-order snapshot."""

        return SubmittedOrderLineSnapshot(
            line_id=self.line_id,
            menu_item_id=self.menu_item_id,
            menu_item_name=self.menu_item_name,
            unit_price=self.unit_price,
            quantity=self.quantity,
            modifiers=self.modifiers,
        )


@dataclass(frozen=True)
class SubmittedOrderLineSnapshot(_LineSnapshotMixin):
    """Permanent submitted-order snapshot."""

    line_id: CartLineId
    menu_item_id: MenuItemId
    menu_item_name: str
    unit_price: Money
    quantity: int
    modifiers: Tuple[CapturedModifierSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not self.menu_item_name.strip():
            raise CartError("Submitted order line item names cannot be empty")
        if self.unit_price.amount < 0:
            raise CartError("Submitted order line prices cannot be negative")
        _validate_money_currency(self.unit_price)
        _validate_line_quantity(self.quantity)
        _validate_unique_modifiers(self.modifiers)
        for modifier in self.modifiers:
            if modifier.price_delta.currency != self.unit_price.currency:
                raise CartError("Submitted order line modifiers must use the same currency")


@dataclass(frozen=True)
class CartReview:
    """Lightweight review summary for a cart."""

    lines: Tuple[CartLineDraftSnapshot, ...]
    line_count: int
    total_units: int


@dataclass(frozen=True)
class Cart:
    """Immutable cart with explicit quantity and size limits."""

    lines: Tuple[CartLineDraftSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_cart_lines(self.lines)

    @classmethod
    def empty(cls) -> "Cart":
        return cls()

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.lines)

    def review(self) -> CartReview:
        return CartReview(
            lines=self.lines, line_count=self.line_count, total_units=self.total_units
        )

    def add_item(
        self,
        menu_item: MenuItem,
        quantity: int = 1,
        modifier_selections: Sequence[ModifierSelectionRequest] = (),
    ) -> "Cart":
        if not menu_item.available:
            raise CartError("Sold-out items cannot be added to the cart")
        _validate_line_quantity(quantity)
        captured_modifiers = menu_item.validate_modifier_selections(modifier_selections)
        candidate = _build_captured_line(CartLineId.new(), menu_item, quantity, captured_modifiers)

        for index, existing_line in enumerate(self.lines):
            if existing_line.signature == candidate.signature:
                merged_quantity = existing_line.quantity + quantity
                if merged_quantity > MAX_LINE_QUANTITY:
                    raise CartLimitError("Cart line quantity exceeds the configured maximum")
                merged_line = CartLineDraftSnapshot(
                    line_id=existing_line.line_id,
                    menu_item_id=existing_line.menu_item_id,
                    menu_item_name=existing_line.menu_item_name,
                    unit_price=existing_line.unit_price,
                    quantity=merged_quantity,
                    modifiers=existing_line.modifiers,
                )
                new_lines = list(self.lines)
                new_lines[index] = merged_line
                return Cart(lines=tuple(new_lines))

        new_lines = (*self.lines, candidate)
        return Cart(lines=new_lines)

    def update_item(
        self,
        line_id: CartLineId,
        quantity: Optional[int] = None,
        menu_item: Optional[MenuItem] = None,
        modifier_selections: Optional[Sequence[ModifierSelectionRequest]] = None,
    ) -> "Cart":
        index = self._line_index(line_id)
        current_line = self.lines[index]
        if menu_item is not None and menu_item.id != current_line.menu_item_id:
            raise CartError("The provided menu item does not match the cart line")

        if quantity is None:
            new_quantity = current_line.quantity
        else:
            _validate_line_quantity(quantity)
            new_quantity = quantity

        if modifier_selections is None:
            captured_modifiers = current_line.modifiers
        else:
            if menu_item is None:
                raise CartError("A menu item is required to update line modifiers")
            captured_modifiers = menu_item.validate_modifier_selections(modifier_selections)

        if new_quantity == current_line.quantity and captured_modifiers == current_line.modifiers:
            return self

        candidate = CartLineDraftSnapshot(
            line_id=current_line.line_id,
            menu_item_id=current_line.menu_item_id,
            menu_item_name=current_line.menu_item_name,
            unit_price=current_line.unit_price,
            quantity=new_quantity,
            modifiers=tuple(captured_modifiers),
        )

        new_lines = list(self.lines)
        new_lines[index] = candidate
        return Cart(lines=_merge_or_replace_lines(tuple(new_lines), candidate, index))

    def remove_item(self, line_id: CartLineId) -> "Cart":
        index = self._line_index(line_id)
        new_lines = list(self.lines)
        del new_lines[index]
        return Cart(lines=tuple(new_lines))

    def clear(self) -> "Cart":
        return Cart.empty()

    def _line_index(self, line_id: CartLineId) -> int:
        for index, line in enumerate(self.lines):
            if line.line_id == line_id:
                return index
        raise CartError("Cart line not found")


def _validate_cart_lines(lines: Sequence[CartLineDraftSnapshot]) -> None:
    if len(lines) > MAX_CART_LINE_COUNT:
        raise CartLimitError("Cart line count exceeds the configured maximum")

    total_units = 0
    signatures: list[Tuple[str, Tuple[Tuple[str, str], ...]]] = []
    for line in lines:
        signatures.append(line.signature)
        total_units += line.quantity

    if len(signatures) != len(set(signatures)):
        raise CartError("Cart cannot contain duplicate line signatures")
    if total_units > MAX_CART_TOTAL_UNITS:
        raise CartLimitError("Cart total units exceed the configured maximum")
