"""Guía del riego (BETA2-JARDIN-04): «siguiente paso» según las métricas.

Lógica PURA compartida por el chip de la cabecera de Foco y la tarjeta
«Siguiente paso» del Cuaderno de cultivo — una sola fuente de verdad para
el umbral débil y la elección de la métrica a reparar (antes triplicados
en watering_panel / cultivation_notebook).
"""

from __future__ import annotations

from dataclasses import dataclass

WEAK_THRESHOLD = 60  # métrica "débil" (misma spec en todo el ciclo de riego)

# Métricas reparables por «Sugerir X» (relevancia la fija el usuario, no la IA).
SUGGESTABLE_METRICS = ("arraigo", "nutrida", "iluminada")

METRIC_LABELS = {
    "arraigo": "Arraigo",
    "nutrida": "Nutrida",
    "iluminada": "Iluminada",
    "relevancia": "Relevancia",
}


@dataclass(frozen=True)
class NextStep:
    """La acción más urgente para la entidad enfocada.

    ``kind``: ``resume`` (secada → cultivar), ``water`` (por regar u obsoleta),
    ``suggest`` (métrica débil, con ``metric``/``score``/``reason``) o
    ``polish`` (todo sano: pasada opcional de calidad).
    """

    kind: str
    metric: str = ""
    score: int | None = None
    reason: str = ""


def next_step(report, threshold: int = WEAK_THRESHOLD) -> NextStep | None:
    """Decide el siguiente paso desde un ``WateringStatusReport`` (o None).

    Prioridad: secada → resume; sin diagnóstico vigente (nunca regada,
    obsoleta o devuelta al ciclo) → water; métrica sugerible más baja bajo el
    umbral → suggest; si no → polish. Empates de métrica: la de menor score
    y, a igualdad, orden alfabético (estable entre refrescos).
    """
    if report is None:
        return None
    status = str(getattr(report, "status", ""))
    if status == "secada":
        return NextStep(kind="resume")
    latest = getattr(report, "latest", None)
    if latest is None or status == "falta_regar":
        return NextStep(kind="water")
    scores = dict(getattr(latest, "scores", {}) or {})
    explanations = dict(getattr(latest, "metric_explanations", {}) or {})
    weak = [
        (int(scores[metric]), metric)
        for metric in SUGGESTABLE_METRICS
        if scores.get(metric) is not None and int(scores[metric]) < threshold
    ]
    if weak:
        score, metric = min(weak)
        return NextStep(
            kind="suggest", metric=metric, score=score, reason=explanations.get(metric, "")
        )
    return NextStep(kind="polish")
