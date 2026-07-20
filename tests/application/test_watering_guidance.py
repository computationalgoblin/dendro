"""Guía del riego (BETA2-JARDIN-04): prioridad del «siguiente paso»."""

from __future__ import annotations

from types import SimpleNamespace

from packages.application.watering_guidance import WEAK_THRESHOLD, NextStep, next_step


def _report(status: str, scores: dict | None = None, explanations: dict | None = None):
    latest = None
    if scores is not None:
        latest = SimpleNamespace(scores=scores, metric_explanations=explanations or {})
    return SimpleNamespace(status=status, latest=latest, stale=False)


class TestNextStep:
    def test_none_report_gives_no_step(self):
        assert next_step(None) is None

    def test_dried_asks_to_resume(self):
        assert next_step(_report("secada", {"arraigo": 10})) == NextStep(kind="resume")

    def test_thirsty_always_asks_to_water_even_with_old_scores(self):
        # Falta regar manda: las métricas antiguas no se consideran.
        step = next_step(_report("falta_regar", {"arraigo": 10, "nutrida": 90}))
        assert step == NextStep(kind="water")
        # Nunca regada (sin diagnóstico) también.
        assert next_step(_report("regada")) == NextStep(kind="water")

    def test_weakest_suggestable_metric_wins(self):
        step = next_step(
            _report(
                "regada",
                {"arraigo": 55, "nutrida": 40, "iluminada": 90, "relevancia": 5},
                {"nutrida": "Le falta contenido propio."},
            )
        )
        assert step is not None
        assert (step.kind, step.metric, step.score) == ("suggest", "nutrida", 40)
        assert step.reason == "Le falta contenido propio."

    def test_relevancia_is_never_suggested(self):
        # La relevancia la fija el usuario: aunque sea bajísima no se sugiere.
        scores = {"arraigo": 80, "nutrida": 80, "iluminada": 80, "relevancia": 5}
        assert next_step(_report("regada", scores)) == NextStep(kind="polish")

    def test_healthy_offers_polish(self):
        scores = {metric: WEAK_THRESHOLD for metric in ("arraigo", "nutrida", "iluminada")}
        assert next_step(_report("regada", scores)) == NextStep(kind="polish")

    def test_score_tie_breaks_alphabetically_stable(self):
        step = next_step(_report("regada", {"nutrida": 30, "arraigo": 30, "iluminada": 90}))
        assert step is not None
        assert step.metric == "arraigo"  # (30, 'arraigo') < (30, 'nutrida')
