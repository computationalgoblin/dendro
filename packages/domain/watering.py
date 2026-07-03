"""Modelos de dominio del sistema de riego — jardín narrativo (BETA2-FOCO).

``Regar`` es un diagnóstico IA autorizado sobre una entidad: produce métricas
(arraigo/nutrida/iluminada/relevancia), informe e historial persistente, pero
NUNCA genera candidatos ni modifica canon. El estado de riego de una entidad
(``WateringStatus``) es DERIVADO por la capa de aplicación a partir de los
timestamps del proyecto y del listado de "secadas" (``Project.watering_paused_entity_ids``);
nunca se persiste por entidad.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WateringMetric(str, Enum):
    """Métricas del diagnóstico de riego."""

    ARRAIGO = "arraigo"
    NUTRIDA = "nutrida"
    ILUMINADA = "iluminada"
    RELEVANCIA = "relevancia"


class WateringCostClass(str, Enum):
    """Clase de coste estimado de una operación IA de riego."""

    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"


class WateringStatus(str, Enum):
    """Estado de riego de una entidad — SIEMPRE derivado, nunca persistido."""

    FALTA_REGAR = "falta_regar"
    REGADA = "regada"
    SECADA = "secada"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return _now()


def _parse_scores(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    scores: dict[str, int] = {}
    for key, raw in value.items():
        try:
            scores[str(key)] = max(0, min(100, int(raw)))
        except (TypeError, ValueError):
            continue
    return scores


def _parse_str_dict(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {}


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


@dataclass
class WateringDiagnostic:
    """Resultado persistente de un riego (o de su fallo trazable en lote).

    ``scores`` mapea ``WateringMetric.value`` → 0..100. La relevancia la define
    el usuario (``narrative_importance`` de la entidad); la IA nunca la impone.
    ``error`` no vacío marca un fallo de lote: la entidad queda "falta regar"
    con causa trazable en su historial de riegos.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    created_at: datetime = field(default_factory=_now)
    scores: dict[str, int] = field(default_factory=dict)
    summary: str = ""
    metric_explanations: dict[str, str] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    context_manifest: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model: str = ""
    cost_class: str = WateringCostClass.BAJO.value
    origin: str = "single"
    author: str = "ia_autorizada"
    resulting_status: str = WateringStatus.REGADA.value
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat(),
            "scores": dict(self.scores),
            "summary": self.summary,
            "metric_explanations": dict(self.metric_explanations),
            "risks": list(self.risks),
            "context_manifest": dict(self.context_manifest),
            "provider": self.provider,
            "model": self.model,
            "cost_class": self.cost_class,
            "origin": self.origin,
            "author": self.author,
            "resulting_status": self.resulting_status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WateringDiagnostic:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            entity_id=str(data.get("entity_id", "")),
            created_at=_parse_datetime(data.get("created_at")),
            scores=_parse_scores(data.get("scores")),
            summary=str(data.get("summary", "")),
            metric_explanations=_parse_str_dict(data.get("metric_explanations")),
            risks=_parse_str_list(data.get("risks")),
            context_manifest=_parse_dict(data.get("context_manifest")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            cost_class=str(data.get("cost_class", WateringCostClass.BAJO.value)),
            origin=str(data.get("origin", "single")),
            author=str(data.get("author", "ia_autorizada")),
            resulting_status=str(
                data.get("resulting_status", WateringStatus.REGADA.value)
            ),
            error=str(data.get("error", "")),
        )
