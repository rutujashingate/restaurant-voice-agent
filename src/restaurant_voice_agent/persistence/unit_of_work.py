"""Unit-of-work wrapper for transactional database work."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .database import SessionFactory
from .repositories import (
    CallSessionRepository,
    CartRepository,
    ComplaintRepository,
    CustomerRepository,
    HandoffRepository,
    IdempotencyRepository,
    MenuRepository,
    OrderRepository,
    OutboxRepository,
    PaymentAttemptRepository,
    PaymentEventRepository,
    PaymentRepository,
    RestaurantRepository,
)


class SqlAlchemyUnitOfWork:
    """Transactional boundary that exposes repositories on demand."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory
        self.session: Session | None = None
        self.restaurants: RestaurantRepository | None = None
        self.menu: MenuRepository | None = None
        self.customers: CustomerRepository | None = None
        self.calls: CallSessionRepository | None = None
        self.carts: CartRepository | None = None
        self.orders: OrderRepository | None = None
        self.payments: PaymentRepository | None = None
        self.payment_attempts: PaymentAttemptRepository | None = None
        self.payment_events: PaymentEventRepository | None = None
        self.complaints: ComplaintRepository | None = None
        self.handoffs: HandoffRepository | None = None
        self.idempotency: IdempotencyRepository | None = None
        self.outbox: OutboxRepository | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self.restaurants = RestaurantRepository(self.session)
        self.menu = MenuRepository(self.session)
        self.customers = CustomerRepository(self.session)
        self.calls = CallSessionRepository(self.session)
        self.carts = CartRepository(self.session)
        self.orders = OrderRepository(self.session)
        self.payments = PaymentRepository(self.session)
        self.payment_attempts = PaymentAttemptRepository(self.session)
        self.payment_events = PaymentEventRepository(self.session)
        self.complaints = ComplaintRepository(self.session)
        self.handoffs = HandoffRepository(self.session)
        self.idempotency = IdempotencyRepository(self.session)
        self.outbox = OutboxRepository(self.session)
        return self

    def commit(self) -> None:
        """Commit the active transaction."""

        self._require_session().commit()

    def rollback(self) -> None:
        """Roll back the active transaction."""

        self._require_session().rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None

    def _require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("The unit of work must be entered before use")
        return self.session


__all__ = ["SqlAlchemyUnitOfWork"]
