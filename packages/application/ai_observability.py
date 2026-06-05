"""AI Observability — B42-T09.

Records metadata for each AI job:
- job_id, intent_type, model, temperature, max_tokens
- context_depth, input_size, output_size, duration_ms
- status, error_type

Never stores API keys. Raw prompt only in explicit debug mode.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIJobRecord:
    """Metadata record for a single AI job."""
    job_id: str
    intent_type: str
    model: str
    temperature: float
    max_tokens: int
    context_depth: int
    input_size: int
    output_size: int
    duration_ms: float
    status: str  # "ok" | "error" | "fallback"
    error_type: str | None = None
    raw_prompt: str | None = None  # Only stored in debug mode

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict. Never includes raw_prompt unless explicitly requested."""
        d = {
            "job_id": self.job_id,
            "intent_type": self.intent_type,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "context_depth": self.context_depth,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_type": self.error_type,
        }
        if self.raw_prompt is not None:
            d["raw_prompt"] = self.raw_prompt
        return d


class AIObservabilityLog:
    """In-memory ring buffer of AI job records.

    Thread-safe for single-process use (desktop app).
    Bounded by max_size to prevent memory growth.
    """

    def __init__(self, max_size: int = 100, debug: bool = False):
        self._records: list[AIJobRecord] = []
        self._max_size = max_size
        self._debug = debug

    @property
    def records(self) -> list[AIJobRecord]:
        return list(self._records)

    @property
    def latest(self) -> AIJobRecord | None:
        return self._records[-1] if self._records else None

    def record(self, entry: AIJobRecord) -> None:
        """Add a job record. Strips raw_prompt unless debug mode."""
        if not self._debug:
            entry.raw_prompt = None
        self._records.append(entry)
        # Ring buffer: trim oldest if over max
        while len(self._records) > self._max_size:
            self._records.pop(0)

    def summary_by_intent(self) -> dict[str, int]:
        """Count of records by intent_type."""
        return dict(Counter(r.intent_type for r in self._records))

    def clear(self) -> None:
        self._records.clear()

    @property
    def size(self) -> int:
        return len(self._records)
