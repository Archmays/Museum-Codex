from __future__ import annotations

import re


class PipelineError(Exception):
    """A stable, user-safe pipeline failure."""

    def __init__(self, code: str, message: str, *, exit_code: int = 3) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = redact_text(message)
        self.exit_code = exit_code


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|authorization|cookie|secret)=([^&\s]+)"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.lower().startswith("(?i)(bearer"):
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub(r"\1=[REDACTED]", redacted)
    return redacted


def contains_unredacted_secret(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS)
