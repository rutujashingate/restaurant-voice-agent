"""Voice session orchestration, fake audio adapters, and call locking."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import ContextManager, Iterator

from restaurant_voice_agent.application.errors import CallLockError
from restaurant_voice_agent.application.ports import (
    CallTransport,
    ConversationLockRegistry,
    SpeechRecognizer,
    SpeechSynthesizer,
)
from restaurant_voice_agent.application.workflow import ConversationWorkflow


@dataclass(frozen=True)
class VoiceInteractionResult:
    """A single voice turn and synthesized response."""

    call_id: str
    user_text: str
    reply_text: str
    audio: bytes
    interrupted: bool = False


class InMemoryConversationLockRegistry:
    """Short-lived per-call lock registry."""

    def __init__(self, lease_seconds: int = 10) -> None:
        self.lease_seconds = lease_seconds
        self._mutex = Lock()
        self._leases: dict[str, datetime] = {}

    def acquire(self, call_id: str) -> ContextManager[bool]:
        @contextmanager
        def _lease() -> Iterator[bool]:
            now = datetime.now(timezone.utc)
            with self._mutex:
                expiry = self._leases.get(call_id)
                if expiry is not None and expiry > now:
                    raise CallLockError(f"Call {call_id!r} is already being handled")
                self._leases[call_id] = now + timedelta(seconds=self.lease_seconds)
            try:
                yield True
            finally:
                with self._mutex:
                    self._leases.pop(call_id, None)

        return _lease()


class FakeSpeechRecognizer:
    """Deterministic speech recognizer used in tests and CI."""

    def __init__(self) -> None:
        self.transcripts: list[str] = []

    def transcribe(self, audio: bytes) -> str:
        text = audio.decode("utf-8")
        self.transcripts.append(text)
        return text


class FakeSpeechSynthesizer:
    """Deterministic speech synthesizer used in tests and CI."""

    def __init__(self) -> None:
        self.spoken_texts: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.spoken_texts.append(text)
        return f"audio:{text}".encode("utf-8")


class FakeCallTransport:
    """A fake call transport that records audio and control events."""

    def __init__(self) -> None:
        self.started_calls: list[str] = []
        self.stopped_calls: list[str] = []
        self.played_audio: list[tuple[str, bytes]] = []

    def start_call(self, call_id: str) -> None:
        self.started_calls.append(call_id)

    def stop_call(self, call_id: str) -> None:
        self.stopped_calls.append(call_id)

    def play_audio(self, call_id: str, audio: bytes) -> None:
        self.played_audio.append((call_id, audio))


class VoiceSessionManager:
    """Manage per-call voice sessions with interruption handling."""

    def __init__(
        self,
        workflow_factory: Callable[[str], ConversationWorkflow],
        recognizer: SpeechRecognizer | None = None,
        synthesizer: SpeechSynthesizer | None = None,
        transport: CallTransport | None = None,
        lock_registry: ConversationLockRegistry | None = None,
    ) -> None:
        self.workflow_factory = workflow_factory
        self.recognizer = recognizer or FakeSpeechRecognizer()
        self.synthesizer = synthesizer or FakeSpeechSynthesizer()
        self.transport = transport or FakeCallTransport()
        self.lock_registry = lock_registry or InMemoryConversationLockRegistry()
        self._workflows: dict[str, ConversationWorkflow] = {}

    def workflow_for(self, call_id: str) -> ConversationWorkflow:
        workflow = self._workflows.get(call_id)
        if workflow is None:
            workflow = self.workflow_factory(call_id)
            self._workflows[call_id] = workflow
        return workflow

    def handle_audio(self, call_id: str, audio: bytes) -> VoiceInteractionResult:
        with self.lock_registry.acquire(call_id):
            self.transport.start_call(call_id)
            workflow = self.workflow_for(call_id)
            user_text = self.recognizer.transcribe(audio)
            response = workflow.respond(user_text)
            response_audio = self.synthesizer.synthesize(response.reply_text)
            self.transport.play_audio(call_id, response_audio)
            return VoiceInteractionResult(
                call_id=call_id,
                user_text=user_text,
                reply_text=response.reply_text,
                audio=response_audio,
                interrupted=False,
            )

    def interrupt(self, call_id: str) -> None:
        self.transport.stop_call(call_id)

    def handle_barge_in(self, call_id: str, audio: bytes) -> VoiceInteractionResult:
        self.interrupt(call_id)
        result = self.handle_audio(call_id, audio)
        return replace(result, interrupted=True)


__all__ = [
    "FakeCallTransport",
    "FakeSpeechRecognizer",
    "FakeSpeechSynthesizer",
    "InMemoryConversationLockRegistry",
    "VoiceInteractionResult",
    "VoiceSessionManager",
]
