"""Validación autoritativa del payload JSON del riego (BETA2-FOCO).

La ruta principal de jobs llama al gateway con ``validate=False`` (deuda
DC-AUDIT-02), así que el diagnóstico de riego valida su propia salida aquí:
``stage_results`` la importa de forma perezosa (patrón coherence_repair) y un
payload inválido produce un error claro — nunca un diagnóstico basura.
"""

from __future__ import annotations

from typing import Any

from packages.domain.result import Error, Ok, Result

_REQUIRED_METRICS = ("arraigo", "nutrida", "iluminada")


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def normalize_watering_payload(payload: Any) -> Result[dict[str, Any], str]:
    """Valida y normaliza el JSON del modelo para un diagnóstico de riego.

    Exige las tres métricas IA (0-100, con clamp) y un resumen no vacío. La
    métrica «relevancia» se DESCARTA si el modelo la cuela: la define el
    usuario (``narrative_importance``), nunca la IA.
    """
    if not isinstance(payload, dict):
        return Error("El diagnóstico de riego debe ser un objeto JSON")

    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, dict):
        return Error("Diagnóstico de riego sin bloque 'scores'")
    scores: dict[str, int] = {}
    for metric in _REQUIRED_METRICS:
        if metric not in raw_scores:
            return Error(f"Falta la métrica '{metric}' en el diagnóstico de riego")
        try:
            scores[metric] = _clamp_score(int(raw_scores[metric]))
        except (TypeError, ValueError):
            return Error(f"La métrica '{metric}' del diagnóstico no es numérica")

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        return Error("Diagnóstico de riego sin resumen")

    raw_explanations = payload.get("metric_explanations")
    explanations: dict[str, str] = {}
    if isinstance(raw_explanations, dict):
        for key, value in raw_explanations.items():
            text = str(value or "").strip()
            if text and str(key) in _REQUIRED_METRICS:
                explanations[str(key)] = text

    raw_risks = payload.get("risks")
    risks: list[str] = []
    if isinstance(raw_risks, list):
        risks = [str(risk).strip() for risk in raw_risks if str(risk or "").strip()]

    # BETA2-STRUCT-09: potencial de propagación causal (0-100) atribuido por la IA de forma
    # semántica. OPCIONAL: si falta o no es numérico → None (el riego sigue igual). El detector
    # estructural lo lee para proponer reubicaciones de anillo.
    raw_pot = payload.get("potencial_causal")
    potencial_causal: int | None = None
    if raw_pot is not None:
        try:
            potencial_causal = _clamp_score(int(raw_pot))
        except (TypeError, ValueError):
            potencial_causal = None

    return Ok(
        {
            "scores": scores,
            "summary": summary,
            "metric_explanations": explanations,
            "risks": risks,
            "potencial_causal": potencial_causal,
        }
    )
