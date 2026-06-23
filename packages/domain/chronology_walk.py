"""Modo Creación Cronológica — modelos de dominio (CRON).

El recorrido guiado hito por hito mantiene una **sesión persistente y reanudable**
(`ChronologyWalkSession`) y produce al final un **informe** (`ChronologyWalkReport`).
Son artefactos de revisión, no canon: la IA nunca muta canon, stagea candidatos por
el pipeline existente. stdlib-only (el dominio no depende de ninguna otra capa).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WalkDirection(str, Enum):
    """Sentido del recorrido sobre el eje temporal (year)."""

    FUTURE = "future"
    PAST = "past"


class WalkMode(str, Enum):
    """Perfil editorial del análisis por hito."""

    CONSISTENCIA = "consistencia"
    CREATIVO = "creativo"
    MIXTO = "mixto"


class WalkDepth(str, Enum):
    """Profundidad del análisis (controla nº de sugerencias / contexto)."""

    LIGERA = "ligera"
    NORMAL = "normal"
    PROFUNDA = "profunda"


class WalkAggressiveness(str, Enum):
    """Cuánto interviene la IA: de solo señalar a proponer piezas nuevas."""

    SENALAR = "solo_senalar"
    REPARAR = "sugerir_reparaciones"
    NUEVAS_PIEZAS = "sugerir_nuevas_piezas"


class WalkStatus(str, Enum):
    """Ciclo de vida de la sesión de recorrido."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class ChronologyWalkSession:
    """Memoria explícita y reanudable de un recorrido cronológico.

    No es memoria libre del modelo: las listas estructuradas
    (`open_problems`, `decisions`, `generated_candidate_ids`) las mantiene el
    servicio; `accumulated_summary` es la prosa acotada regenerada por paso.
    """

    id: str = field(default_factory=lambda: f"walk_{uuid.uuid4().hex[:10]}")
    direction: WalkDirection = WalkDirection.FUTURE
    mode: WalkMode = WalkMode.MIXTO
    depth: WalkDepth = WalkDepth.NORMAL
    aggressiveness: WalkAggressiveness = WalkAggressiveness.REPARAR
    start_milestone_id: str = ""
    current_milestone_id: str = ""
    visited_milestone_ids: list[str] = field(default_factory=list)
    accumulated_summary: str = ""
    open_problems: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    generated_candidate_ids: list[str] = field(default_factory=list)
    last_narrative_state: dict[str, Any] = field(default_factory=dict)
    status: WalkStatus = WalkStatus.ACTIVE
    report_id: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "direction": self.direction.value,
            "mode": self.mode.value,
            "depth": self.depth.value,
            "aggressiveness": self.aggressiveness.value,
            "start_milestone_id": self.start_milestone_id,
            "current_milestone_id": self.current_milestone_id,
            "visited_milestone_ids": list(self.visited_milestone_ids),
            "accumulated_summary": self.accumulated_summary,
            "open_problems": [dict(p) for p in self.open_problems],
            "decisions": [dict(d) for d in self.decisions],
            "generated_candidate_ids": list(self.generated_candidate_ids),
            "last_narrative_state": dict(self.last_narrative_state),
            "status": self.status.value,
            "report_id": self.report_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChronologyWalkSession:
        raw_id = data.get("id")
        report_id = data.get("report_id")
        fallback_id = f"walk_{uuid.uuid4().hex[:10]}"
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else fallback_id,
            direction=_parse_enum(WalkDirection, data.get("direction"), WalkDirection.FUTURE),
            mode=_parse_enum(WalkMode, data.get("mode"), WalkMode.MIXTO),
            depth=_parse_enum(WalkDepth, data.get("depth"), WalkDepth.NORMAL),
            aggressiveness=_parse_enum(
                WalkAggressiveness, data.get("aggressiveness"), WalkAggressiveness.REPARAR
            ),
            start_milestone_id=str(data.get("start_milestone_id", "")),
            current_milestone_id=str(data.get("current_milestone_id", "")),
            visited_milestone_ids=_parse_str_list(data.get("visited_milestone_ids")),
            accumulated_summary=str(data.get("accumulated_summary", "")),
            open_problems=_parse_dict_list(data.get("open_problems")),
            decisions=_parse_dict_list(data.get("decisions")),
            generated_candidate_ids=_parse_str_list(data.get("generated_candidate_ids")),
            last_narrative_state=_parse_dict(data.get("last_narrative_state")),
            status=_parse_enum(WalkStatus, data.get("status"), WalkStatus.ACTIVE),
            report_id=report_id if isinstance(report_id, str) and report_id.strip() else None,
            created_at=str(data.get("created_at", "")) or _now_iso(),
            updated_at=str(data.get("updated_at", "")) or _now_iso(),
            metadata=_parse_dict(data.get("metadata")),
        )


@dataclass
class ChronologyWalkReport:
    """Informe persistido al terminar (o detener) un recorrido.

    Artefacto de revisión, no canon: documenta qué se revisó y qué queda.
    """

    id: str = field(default_factory=lambda: f"walkrep_{uuid.uuid4().hex[:10]}")
    session_id: str = ""
    direction: WalkDirection = WalkDirection.FUTURE
    mode: WalkMode = WalkMode.MIXTO
    range_start_milestone_id: str = ""
    range_end_milestone_id: str = ""
    milestones_analyzed: list[str] = field(default_factory=list)
    verdict: str = ""
    critical_gaps: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    candidates_created: list[str] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    timeline_reviewed_up_to_milestone_id: str = ""
    recommended_next_steps: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "direction": self.direction.value,
            "mode": self.mode.value,
            "range_start_milestone_id": self.range_start_milestone_id,
            "range_end_milestone_id": self.range_end_milestone_id,
            "milestones_analyzed": list(self.milestones_analyzed),
            "verdict": self.verdict,
            "critical_gaps": [dict(g) for g in self.critical_gaps],
            "contradictions": [dict(c) for c in self.contradictions],
            "candidates_created": list(self.candidates_created),
            "decisions": [dict(d) for d in self.decisions],
            "timeline_reviewed_up_to_milestone_id": self.timeline_reviewed_up_to_milestone_id,
            "recommended_next_steps": list(self.recommended_next_steps),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChronologyWalkReport:
        raw_id = data.get("id")
        return cls(
            id=raw_id
            if isinstance(raw_id, str) and raw_id.strip()
            else f"walkrep_{uuid.uuid4().hex[:10]}",
            session_id=str(data.get("session_id", "")),
            direction=_parse_enum(WalkDirection, data.get("direction"), WalkDirection.FUTURE),
            mode=_parse_enum(WalkMode, data.get("mode"), WalkMode.MIXTO),
            range_start_milestone_id=str(data.get("range_start_milestone_id", "")),
            range_end_milestone_id=str(data.get("range_end_milestone_id", "")),
            milestones_analyzed=_parse_str_list(data.get("milestones_analyzed")),
            verdict=str(data.get("verdict", "")),
            critical_gaps=_parse_dict_list(data.get("critical_gaps")),
            contradictions=_parse_dict_list(data.get("contradictions")),
            candidates_created=_parse_str_list(data.get("candidates_created")),
            decisions=_parse_dict_list(data.get("decisions")),
            timeline_reviewed_up_to_milestone_id=str(
                data.get("timeline_reviewed_up_to_milestone_id", "")
            ),
            recommended_next_steps=_parse_str_list(data.get("recommended_next_steps")),
            created_at=str(data.get("created_at", "")) or _now_iso(),
            metadata=_parse_dict(data.get("metadata")),
        )


def _parse_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


__all__ = [
    "ChronologyWalkReport",
    "ChronologyWalkSession",
    "WalkAggressiveness",
    "WalkDepth",
    "WalkDirection",
    "WalkMode",
    "WalkStatus",
]
