"""Human handoff and escalation services."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.models import HandoffSummary
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.persistence.models import HandoffRecord


@dataclass(frozen=True)
class HandoffRequest:
    """Input for creating a human handoff."""

    restaurant_id: str
    reason: str
    destination: str | None = None
    order_id: str | None = None
    customer_id: str | None = None
    notes: str | None = None


class HandoffService:
    """Capture human handoffs in a structured, retrievable form."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    def create_handoff(self, request: HandoffRequest) -> HandoffSummary:
        with self.uow_factory() as uow:
            if request.order_id is not None and uow.orders.get(request.order_id) is None:
                raise NotFoundError(f"Order {request.order_id!r} was not found")

            digest = hashlib.sha256(
                "|".join(
                    [
                        request.restaurant_id,
                        request.reason,
                        request.destination or "",
                        request.order_id or "",
                        request.customer_id or "",
                        request.notes or "",
                    ]
                ).encode("utf-8")
            ).hexdigest()[:16]
            record = uow.handoffs.upsert(
                HandoffRecord(
                    id=f"handoff_{request.restaurant_id}_{digest}",
                    restaurant_id=request.restaurant_id,
                    order_id=request.order_id,
                    customer_id=request.customer_id,
                    reason=request.reason,
                    destination=request.destination,
                    status="PENDING",
                    notes=request.notes,
                )
            )
            return HandoffSummary(
                handoff_id=record.id,
                status=record.status,
                reason=record.reason,
                destination=record.destination,
                order_id=record.order_id,
                complaint_id=None,
                notes=record.notes,
            )

    def get_handoff(self, handoff_id: str) -> HandoffSummary:
        with self.uow_factory() as uow:
            record = uow.handoffs.get(handoff_id)
            if record is None:
                raise NotFoundError(f"Handoff {handoff_id!r} was not found")
            return HandoffSummary(
                handoff_id=record.id,
                status=record.status,
                reason=record.reason,
                destination=record.destination,
                order_id=record.order_id,
                complaint_id=None,
                notes=record.notes,
            )
