"""Structured Coherence Output — B42-T08.

Provides an optional structured representation of coherence analysis results.
Maintains compatibility with the existing raw text output.

Can be used alongside raw text — the structured view is derived from parsing
or can be constructed directly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CoherenceSeverity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CoherenceFinding:
    """A single finding from coherence analysis."""
    topic: str
    issue: str
    severity: CoherenceSeverity = CoherenceSeverity.INFO
    evidence: str = ""
    repair_options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "issue": self.issue,
            "severity": self.severity.value,
            "evidence": self.evidence,
            "repair_options": self.repair_options,
        }


@dataclass
class CoherenceResult:
    """Structured coherence analysis result."""
    verdict: str
    findings: list[CoherenceFinding] = field(default_factory=list)
    severity: CoherenceSeverity = CoherenceSeverity.OK
    raw_text: str = ""
    repair_options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "findings": [f.to_dict() for f in self.findings],
            "severity": self.severity.value,
            "raw_text": self.raw_text,
            "repair_options": self.repair_options,
        }


def parse_coherence_text(text: str) -> CoherenceResult:
    """Parse raw coherence analysis text into structured result.

    Best-effort extraction of verdict and findings from the structured
    sections that coherence prompts ask for. Falls back gracefully
    if sections aren't found.
    """
    if not text or not text.strip():
        return CoherenceResult(verdict="unknown", raw_text=text or "")

    # Try to extract verdict
    verdict = "unknown"
    verdict_match = re.search(
        r"(?:veredicto|verdict)[:\s]+(.*?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if verdict_match:
        verdict = verdict_match.group(1).strip()[:100]

    # Try to determine severity from text
    severity = CoherenceSeverity.OK
    text_lower = text.lower()
    if "contradicción" in text_lower or "contradiction" in text_lower:
        severity = CoherenceSeverity.CRITICAL
    elif "hueco" in text_lower or "gap" in text_lower:
        severity = CoherenceSeverity.WARNING
    elif "problema" in text_lower or "problem" in text_lower:
        severity = CoherenceSeverity.WARNING

    # Extract findings from Contradictions/Issues sections
    findings: list[CoherenceFinding] = []
    finding_sections = re.findall(
        r"(?:contradicci[oó]n|hueco|gap|problema|issue)[:\s\-]+(.*?)(?:\n|$)",
        text, re.IGNORECASE
    )
    for f_text in finding_sections:
        if f_text.strip():
            findings.append(CoherenceFinding(
                topic="",
                issue=f_text.strip()[:200],
                severity=CoherenceSeverity.WARNING,
            ))

    return CoherenceResult(
        verdict=verdict,
        findings=findings,
        severity=severity,
        raw_text=text,
    )
