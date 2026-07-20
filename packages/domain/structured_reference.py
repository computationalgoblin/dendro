"""Referencias estructuradas transversales (BETA2-MEM-03).

Una @mencion que el usuario escribe en un campo de prosa se convierte, AL GUARDAR,
en una ``StructuredReference``: un puntero estable ``(target_kind, target_id)`` a un
elemento del proyecto, independiente del nombre visible (renombrado seguro). Las
referencias alimentan backlinks, motor de impacto (MEM-04) y contexto IA (MEM-06)
sin crear una wiki paralela ni importar documentos.

Modelo **sidecar**: el texto se guarda tal cual (con el ``@alias`` que teclea el
usuario); la referencia resuelta vive aparte, en la coleccion del proyecto
``structured_references``. Dominio puro (stdlib-only). Reutiliza ``MemoryTargetKind``
como vocabulario canonico de tipos de elemento (introducido en MEM-02); no se crea un
enum paralelo. ``MemoryCitation`` es el hermano de esta referencia en el ambito de
Memoria (mismo ``ref_kind``/``ref_id``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.domain.narrative_memory import MemoryTargetKind


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"ref_{uuid.uuid4().hex[:10]}"


class ReferenceStatus(str, Enum):
    """Estado de resolucion de una @mencion (contrato memoria_narrativa.md §10).

    - ``RESUELTA``: apunta sin ambiguedad a un ``target_id`` estable.
    - ``AMBIGUA``: el nombre casa con varios elementos; NO se elige uno en
      silencio (``target_id`` vacio, candidatos en ``candidate_target_ids``).
    - ``NO_RESUELTA``: el nombre no casa con ningun elemento; queda reparable
      sin romper el guardado (nunca crea canon).
    """

    RESUELTA = "resuelta"
    AMBIGUA = "ambigua"
    NO_RESUELTA = "no_resuelta"


def _parse_enum(enum_cls: type[Enum], value: Any, default: Any) -> Any:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


@dataclass
class StructuredReference:
    """Una @mencion resuelta: quien la escribe (source) apunta a que (target).

    ``source_*`` localizan el campo de prosa donde se escribio la mencion (para
    backlinks e impacto). ``target_*`` son el puntero estable por id. ``alias`` es
    el texto visible tecleado (para resaltar y para reparar menciones ambiguas/no
    resueltas). El renombrado del target no rompe la referencia porque apunta a id.
    """

    id: str = field(default_factory=_new_id)
    source_kind: MemoryTargetKind = MemoryTargetKind.ENTITY
    source_id: str = ""
    source_field: str = ""
    target_kind: MemoryTargetKind = MemoryTargetKind.ENTITY
    target_id: str = ""  # vacio cuando AMBIGUA o NO_RESUELTA
    alias: str = ""
    status: ReferenceStatus = ReferenceStatus.RESUELTA
    candidate_target_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_resolved(self) -> bool:
        return self.status == ReferenceStatus.RESUELTA and bool(self.target_id)

    def source_key(self) -> tuple[str, str]:
        """Identidad del emisor de la mencion (nivel + id)."""
        return (self.source_kind.value, self.source_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_kind": self.source_kind.value,
            "source_id": self.source_id,
            "source_field": self.source_field,
            "target_kind": self.target_kind.value,
            "target_id": self.target_id,
            "alias": self.alias,
            "status": self.status.value,
            "candidate_target_ids": list(self.candidate_target_ids),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredReference:
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else _new_id(),
            source_kind=_parse_enum(
                MemoryTargetKind, data.get("source_kind"), MemoryTargetKind.ENTITY
            ),
            source_id=_parse_str(data.get("source_id")),
            source_field=_parse_str(data.get("source_field")),
            target_kind=_parse_enum(
                MemoryTargetKind, data.get("target_kind"), MemoryTargetKind.ENTITY
            ),
            target_id=_parse_str(data.get("target_id")),
            alias=_parse_str(data.get("alias")),
            status=_parse_enum(ReferenceStatus, data.get("status"), ReferenceStatus.RESUELTA),
            candidate_target_ids=_parse_str_list(data.get("candidate_target_ids")),
            created_at=_parse_str(data.get("created_at")) or _now_iso(),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )


__all__ = ["ReferenceStatus", "StructuredReference"]
