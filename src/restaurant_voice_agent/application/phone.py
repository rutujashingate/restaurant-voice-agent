"""Phone-call routing and human handoff helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from restaurant_voice_agent.application.errors import NotFoundError
from restaurant_voice_agent.application.handoffs import HandoffRequest, HandoffService
from restaurant_voice_agent.application.models import HandoffSummary
from restaurant_voice_agent.application.ports import UnitOfWork
from restaurant_voice_agent.application.voice import (
    VoiceInteractionResult,
    VoiceSessionManager,
)
from restaurant_voice_agent.persistence.models import CallSessionRecord


@dataclass(frozen=True)
class IncomingCallRequest:
    """Normalized inbound phone call request."""

    restaurant_id: str
    provider_call_id: str
    from_phone: str
    to_phone: str


@dataclass(frozen=True)
class CallContext:
    """Resolved call metadata used to build the voice workflow."""

    call_session_id: str
    restaurant_id: str
    customer_id: str | None
    customer_phone: str


@dataclass(frozen=True)
class PhoneRoutingResult:
    """The outcome of resolving an inbound call."""

    call_session_id: str
    customer_id: str | None
    greeting: str


@dataclass(frozen=True)
class TransferResult:
    """The outcome of a human handoff attempt."""

    summary: HandoffSummary
    transferred: bool
    message: str


class PhoneCallManager:
    """Resolve callers, map provider threads to call sessions, and manage handoffs."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        voice_session_manager: VoiceSessionManager,
        handoff_service: HandoffService,
        transfer_handler: Callable[[str, HandoffSummary], None] | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.voice_session_manager = voice_session_manager
        self.handoff_service = handoff_service
        self.transfer_handler = transfer_handler
        self.thread_to_call: dict[str, str] = {}
        self.call_contexts: dict[str, CallContext] = {}

    def register_incoming_call(self, request: IncomingCallRequest) -> PhoneRoutingResult:
        with self.uow_factory() as uow:
            customer = uow.customers.find_by_phone_number(request.restaurant_id, request.from_phone)
            call_session_id = f"call_{request.provider_call_id}"
            uow.calls.upsert(
                CallSessionRecord(
                    id=call_session_id,
                    restaurant_id=request.restaurant_id,
                    customer_id=customer.id if customer is not None else None,
                    provider_call_id=request.provider_call_id,
                    channel="voice",
                    status="OPEN",
                    notes="Inbound call routed through the phone manager.",
                )
            )
            self.thread_to_call[request.provider_call_id] = call_session_id
            self.call_contexts[request.provider_call_id] = CallContext(
                call_session_id=call_session_id,
                restaurant_id=request.restaurant_id,
                customer_id=customer.id if customer is not None else None,
                customer_phone=request.from_phone,
            )
            greeting = (
                "Welcome back." if customer is not None else "Welcome to Copper Spoon Kitchen."
            )
            return PhoneRoutingResult(
                call_session_id=call_session_id,
                customer_id=customer.id if customer is not None else None,
                greeting=greeting,
            )

    def handle_audio(self, provider_call_id: str, audio: bytes) -> VoiceInteractionResult:
        if provider_call_id not in self.call_contexts:
            raise NotFoundError(f"Call {provider_call_id!r} has not been registered")
        return self.voice_session_manager.handle_audio(provider_call_id, audio)

    def transfer_to_human(self, provider_call_id: str, reason: str) -> TransferResult:
        context = self.call_contexts.get(provider_call_id)
        if context is None:
            raise NotFoundError(f"Call {provider_call_id!r} has not been registered")

        summary = self.handoff_service.create_handoff(
            HandoffRequest(
                restaurant_id=context.restaurant_id,
                reason=reason,
                customer_id=context.customer_id,
            )
        )
        transferred = True
        message = "Transferred to a person on the team."
        if self.transfer_handler is not None:
            try:
                self.transfer_handler(provider_call_id, summary)
            except Exception:
                transferred = False
                message = "I saved the handoff request and will let the restaurant team follow up."
        return TransferResult(summary=summary, transferred=transferred, message=message)

    def get_call_session_id(self, provider_call_id: str) -> str | None:
        return self.thread_to_call.get(provider_call_id)


__all__ = [
    "CallContext",
    "IncomingCallRequest",
    "PhoneCallManager",
    "PhoneRoutingResult",
    "TransferResult",
]
