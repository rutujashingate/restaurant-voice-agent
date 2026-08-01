"""Simple log and report redaction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PHONE_PATTERN = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_LONG_ID_PATTERN = re.compile(r"\b[a-f0-9]{16,}\b", re.IGNORECASE)
_STRIPE_SECRET_PATTERN = re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")


@dataclass(frozen=True)
class Redactor:
    """Redact sensitive values from text."""

    replacement: str = "[REDACTED]"

    def redact(self, text: str) -> str:
        redacted = _PHONE_PATTERN.sub(self.replacement, text)
        redacted = _EMAIL_PATTERN.sub(self.replacement, redacted)
        redacted = _LONG_ID_PATTERN.sub(self.replacement, redacted)
        redacted = _STRIPE_SECRET_PATTERN.sub(self.replacement, redacted)
        return redacted
