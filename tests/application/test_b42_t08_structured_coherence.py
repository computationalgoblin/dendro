"""Tests for B42-T08: Structured coherence output.

Optional structured output for coherence analysis with:
verdict, findings, severity, evidence, repair_options.
Maintains compatibility with textual output.
"""
import pytest

from packages.application.structured_coherence import (
    CoherenceResult,
    CoherenceFinding,
    CoherenceSeverity,
    parse_coherence_text,
)


class TestCoherenceResult:
    def test_result_has_all_fields(self):
        r = CoherenceResult(
            verdict="coherent",
            findings=[],
            severity=CoherenceSeverity.OK,
            raw_text="All good",
        )
        assert r.verdict == "coherent"
        assert r.severity == CoherenceSeverity.OK
        assert r.raw_text == "All good"

    def test_result_to_dict(self):
        r = CoherenceResult(
            verdict="issues_found",
            findings=[CoherenceFinding(topic="Fosco", issue="No motivation", severity=CoherenceSeverity.WARNING)],
            severity=CoherenceSeverity.WARNING,
            raw_text="Problems found",
        )
        d = r.to_dict()
        assert d["verdict"] == "issues_found"
        assert len(d["findings"]) == 1
        assert d["findings"][0]["topic"] == "Fosco"
        assert d["severity"] == "warning"

    def test_result_from_text(self):
        text = "Veredicto: coherente. No se encontraron contradicciones."
        r = parse_coherence_text(text)
        assert r.raw_text == text
        assert r.verdict is not None


class TestCoherenceFinding:
    def test_finding_fields(self):
        f = CoherenceFinding(
            topic="Fosco",
            issue="Falta motivación",
            severity=CoherenceSeverity.WARNING,
            evidence="Sin antecedentes de viaje",
            repair_options=["Añadir backstory de viaje"],
        )
        assert f.topic == "Fosco"
        assert f.severity == CoherenceSeverity.WARNING
        assert len(f.repair_options) == 1

    def test_finding_to_dict(self):
        f = CoherenceFinding(topic="Bilbo", issue="Contradicción", severity=CoherenceSeverity.CRITICAL)
        d = f.to_dict()
        assert d["severity"] == "critical"


class TestParseCoherenceText:
    def test_parse_spanish_coherent(self):
        text = "Veredicto global: COHERENTE. No se detectan contradicciones."
        r = parse_coherence_text(text)
        assert "coherente" in r.verdict.lower() or r.verdict == "unknown"
        assert r.raw_text == text

    def test_parse_spanish_issues(self):
        text = "Veredicto: PROBLEMAS. Contradicción: Fosco dice X pero hizo Y."
        r = parse_coherence_text(text)
        assert r.raw_text == text

    def test_parse_empty_returns_unknown(self):
        r = parse_coherence_text("")
        assert r.verdict == "unknown"

    def test_parse_preserves_raw_text(self):
        text = "Some arbitrary coherence text"
        r = parse_coherence_text(text)
        assert r.raw_text == text
