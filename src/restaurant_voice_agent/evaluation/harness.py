"""Evaluation harness for conversation scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from restaurant_voice_agent.application.models import (
    ConversationTurnResult,
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationReport,
)
from restaurant_voice_agent.application.workflow import ConversationWorkflow
from restaurant_voice_agent.evaluation.redaction import Redactor


@dataclass(frozen=True)
class EvaluationRun:
    """A single evaluation execution."""

    report: EvaluationReport
    redacted_transcript: tuple[str, ...]


class EvaluationHarness:
    """Run repeatable conversation scenarios and score the outcomes."""

    def __init__(
        self,
        workflow_factory: Callable[[str], ConversationWorkflow],
        redactor: Redactor | None = None,
    ) -> None:
        self.workflow_factory = workflow_factory
        self.redactor = redactor or Redactor()

    def run_case(self, case: EvaluationCase) -> EvaluationCaseResult:
        workflow = self.workflow_factory(case.name)
        transcript: list[ConversationTurnResult] = []
        notes: list[str] = []

        for utterance in case.utterances:
            result = workflow.respond(utterance)
            transcript.append(result)

        if case.expected_topics and len(case.expected_topics) != len(transcript):
            notes.append(
                "Expected topics and transcript length differ; the case may be under-specified."
            )

        passed = True
        for expected_topic, result in zip(case.expected_topics, transcript, strict=False):
            if result.topic != expected_topic:
                passed = False
                notes.append(f"Expected topic {expected_topic!r} but saw {result.topic!r}.")

        combined_reply = " ".join(result.reply_text for result in transcript)
        for phrase in case.expected_phrases:
            if phrase.lower() not in combined_reply.lower():
                passed = False
                notes.append(f"Missing expected phrase {phrase!r}.")

        return EvaluationCaseResult(
            case_name=case.name,
            passed=passed,
            transcript=tuple(transcript),
            notes=tuple(notes),
        )

    def run(self, name: str, cases: Iterable[EvaluationCase]) -> EvaluationReport:
        case_results = tuple(self.run_case(case) for case in cases)
        return EvaluationReport(
            name=name,
            case_results=case_results,
            generated_at=datetime.now(timezone.utc),
        )

    def render_redacted_transcript(
        self, transcript: Iterable[ConversationTurnResult]
    ) -> tuple[str, ...]:
        return tuple(self.redactor.redact(result.reply_text) for result in transcript)


__all__ = ["EvaluationHarness", "EvaluationRun"]
