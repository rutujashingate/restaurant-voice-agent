"""Complaint capture services."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.models import ComplaintSummary
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.domain.enums import ComplaintCategory
from restaurant_voice_agent.persistence.models import ComplaintRecord


@dataclass(frozen=True)
class ComplaintRequest:
    """Input for opening a complaint."""

    restaurant_id: str
    category: ComplaintCategory
    notes: str
    order_id: str | None = None
    customer_id: str | None = None


class ComplaintService:
    """Create and read complaint records."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    def create_complaint(self, request: ComplaintRequest) -> ComplaintSummary:
        with self.uow_factory() as uow:
            if request.order_id is not None and uow.orders.get(request.order_id) is None:
                raise NotFoundError(f"Order {request.order_id!r} was not found")

            digest = hashlib.sha256(
                "|".join(
                    [
                        request.restaurant_id,
                        request.category.value,
                        request.order_id or "",
                        request.customer_id or "",
                        request.notes,
                    ]
                ).encode("utf-8")
            ).hexdigest()[:16]
            record = uow.complaints.upsert(
                ComplaintRecord(
                    id=f"complaint_{request.restaurant_id}_{digest}",
                    restaurant_id=request.restaurant_id,
                    order_id=request.order_id,
                    customer_id=request.customer_id,
                    category=request.category.value,
                    status="OPEN",
                    notes=request.notes,
                )
            )
            return ComplaintSummary(
                complaint_id=record.id,
                display_number=record.display_number,
                category=record.category,
                status=record.status,
                order_id=record.order_id,
                notes=record.notes,
            )

    def get_complaint(self, complaint_id: str) -> ComplaintSummary:
        with self.uow_factory() as uow:
            record = uow.complaints.get(complaint_id)
            if record is None:
                raise NotFoundError(f"Complaint {complaint_id!r} was not found")
            return ComplaintSummary(
                complaint_id=record.id,
                display_number=record.display_number,
                category=record.category,
                status=record.status,
                order_id=record.order_id,
                notes=record.notes,
            )
