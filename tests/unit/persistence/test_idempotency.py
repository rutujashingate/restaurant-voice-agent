"""Tests for idempotency protection."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from restaurant_voice_agent.persistence.errors import IdempotencyConflictError
from restaurant_voice_agent.persistence.models import IdempotencyKeyRecord
from restaurant_voice_agent.persistence.repositories import IdempotencyRepository


def _count(session) -> int:
    return session.scalar(select(func.count()).select_from(IdempotencyKeyRecord)) or 0


def test_idempotency_repository_rejects_hash_mismatch(session) -> None:
    repository = IdempotencyRepository(session)

    repository.record_response(
        scope="checkout",
        key="demo_idempotency_key",
        request_hash="hash-one",
        response_status=200,
        response_body={"status": "ok"},
    )

    with pytest.raises(IdempotencyConflictError):
        repository.record_response(
            scope="checkout",
            key="demo_idempotency_key",
            request_hash="hash-two",
            response_status=200,
            response_body={"status": "different"},
        )

    assert _count(session) == 1


def test_idempotency_repository_updates_matching_hash(session) -> None:
    repository = IdempotencyRepository(session)

    repository.record_response(
        scope="checkout",
        key="demo_idempotency_key",
        request_hash="hash-one",
        response_status=200,
        response_body={"status": "ok"},
    )
    updated = repository.record_response(
        scope="checkout",
        key="demo_idempotency_key",
        request_hash="hash-one",
        response_status=201,
        response_body={"status": "updated"},
    )

    assert updated.response_status == 201
    assert updated.response_body == {"status": "updated"}
    assert _count(session) == 1
