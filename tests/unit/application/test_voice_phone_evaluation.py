"""Tests for voice handling, phone routing, and evaluation redaction."""

from __future__ import annotations

import pytest

from restaurant_voice_agent.application.errors import CallLockError
from restaurant_voice_agent.application.handoffs import HandoffService
from restaurant_voice_agent.application.models import ConversationTurnResult, EvaluationCase
from restaurant_voice_agent.application.phone import (
    IncomingCallRequest,
    PhoneCallManager,
)
from restaurant_voice_agent.application.voice import (
    FakeCallTransport,
    InMemoryConversationLockRegistry,
    VoiceSessionManager,
)
from restaurant_voice_agent.evaluation import EvaluationHarness, Redactor

from .helpers import CUSTOMER_PHONE, seed_customer, seed_restaurant_catalog


class EchoWorkflow:
    """A tiny workflow stub used in tests."""

    def __init__(self, call_id: str) -> None:
        self.call_id = call_id

    def respond(self, user_text: str) -> ConversationTurnResult:
        return ConversationTurnResult(reply_text=f"echo: {user_text}", topic="echo")


def test_voice_session_manager_handles_barge_in_and_locking() -> None:
    transport = FakeCallTransport()
    manager = VoiceSessionManager(lambda call_id: EchoWorkflow(call_id), transport=transport)

    first = manager.handle_audio("call_1", b"hello")
    barged = manager.handle_barge_in("call_1", b"interrupt")

    assert first.reply_text == "echo: hello"
    assert first.interrupted is False
    assert barged.interrupted is True
    assert transport.started_calls == ["call_1", "call_1"]
    assert transport.stopped_calls == ["call_1"]
    assert transport.played_audio[0][0] == "call_1"

    registry = InMemoryConversationLockRegistry(lease_seconds=60)
    with registry.acquire("call_2"):
        with pytest.raises(CallLockError):
            with registry.acquire("call_2"):
                pass


def test_phone_call_manager_routes_calls_and_creates_handoffs(uow_factory, session) -> None:
    restaurant_id, _, _ = seed_restaurant_catalog(session)
    seed_customer(session, restaurant_id)

    voice_manager = VoiceSessionManager(lambda call_id: EchoWorkflow(call_id))
    handoff_service = HandoffService(uow_factory)

    def failing_transfer_handler(call_id: str, summary) -> None:
        del call_id, summary
        raise RuntimeError("transfer failed")

    manager = PhoneCallManager(
        uow_factory,
        voice_manager,
        handoff_service,
        transfer_handler=failing_transfer_handler,
    )

    routing = manager.register_incoming_call(
        IncomingCallRequest(
            restaurant_id=restaurant_id,
            provider_call_id="twilio_call_1",
            from_phone=CUSTOMER_PHONE,
            to_phone="+1-602-555-0148",
        )
    )
    assert routing.greeting == "Welcome back."
    assert routing.customer_id == "maya_patel"
    assert manager.get_call_session_id("twilio_call_1") == "call_twilio_call_1"

    voice_reply = manager.handle_audio("twilio_call_1", b"hello")
    assert voice_reply.reply_text == "echo: hello"

    transfer = manager.transfer_to_human("twilio_call_1", "customer wants help")
    assert transfer.transferred is False
    assert "saved the handoff request" in transfer.message

    with uow_factory() as uow:
        handoffs = uow.handoffs.list()

    assert len(handoffs) == 1
    assert handoffs[0].reason == "customer wants help"


def test_evaluation_harness_redacts_sensitive_data_and_scores_case() -> None:
    harness = EvaluationHarness(lambda call_id: EchoWorkflow(call_id))
    redactor = Redactor()
    case = EvaluationCase(
        name="echo",
        utterances=("hello",),
        expected_topics=("echo",),
        expected_phrases=("echo: hello",),
    )

    result = harness.run_case(case)
    report = harness.run("demo", (case,))
    redacted = harness.render_redacted_transcript(
        (
            ConversationTurnResult(
                reply_text=(
                    "Call +1 (602) 555-0188 or jane@example.com about sk_test_1234567890abcdef"
                ),
                topic="echo",
            ),
        )
    )

    assert result.passed is True
    assert report.passed is True
    assert "[REDACTED]" in redacted[0]
    assert redactor.redact("Call +1 602-555-0188") == "Call [REDACTED]"
