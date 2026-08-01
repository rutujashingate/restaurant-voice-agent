"""Database persistence layer for the restaurant voice agent."""

from .database import (
    create_engine_from_settings,
    create_engine_from_url,
    create_session_factory,
    get_database_url,
)
from .errors import DatabaseConfigurationError, PersistenceError, RepositoryError, SeedError
from .models import Base
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
from .seed import seed_demo_data
from .unit_of_work import SqlAlchemyUnitOfWork

__all__ = [
    "Base",
    "CallSessionRepository",
    "CartRepository",
    "ComplaintRepository",
    "CustomerRepository",
    "DatabaseConfigurationError",
    "HandoffRepository",
    "IdempotencyRepository",
    "MenuRepository",
    "OrderRepository",
    "OutboxRepository",
    "PaymentAttemptRepository",
    "PaymentEventRepository",
    "PaymentRepository",
    "PersistenceError",
    "RepositoryError",
    "RestaurantRepository",
    "SeedError",
    "SqlAlchemyUnitOfWork",
    "create_engine_from_settings",
    "create_engine_from_url",
    "create_session_factory",
    "get_database_url",
    "seed_demo_data",
]
