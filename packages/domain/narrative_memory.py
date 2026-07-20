"""Memoria narrativa viva — modelos de dominio (BETA2-MEM-02).

La Memoria es un estado **derivado**, editorial, persistente y consultable que
resume la lectura actual del proyecto. **No es canon**: la IA nunca la convierte
en canon y una referencia estructurada tiene más autoridad que una frase suelta
de Memoria (contrato ``docs/contracts/memoria_narrativa.md`` §2).

Este módulo es dominio puro (stdlib-only, sin dependencias de otras capas). No
llama a IA ni renderiza UI: solo modela y serializa. El servicio de aplicación
(``NarrativeMemoryService``) muta el ``Project``; la UI nunca escribe persistencia.

Niveles (contrato §3): proyecto, entidad, relación, hito, anillo y rama. La
memoria **contextual** (una entidad que cambia de rol según época, escenario o
conflicto) no es un nivel aparte: es un target concreto con ``context`` no vacío.
Un único modelo genérico ``NarrativeMemory`` cubre todos los niveles mediante la
clave estable ``(target_kind, target_id, context)``, sin duplicar entidades,
hitos, relaciones ni anillos (regla del repo: "no crear modelos paralelos").
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class MemoryTargetKind(str, Enum):
    """A qué elemento del proyecto pertenece un bloque de Memoria.

    La memoria *contextual* no es un kind propio: es un target concreto (p. ej.
    ``ENTITY``) con ``context`` no vacío.
    """

    PROJECT = "project"
    ENTITY = "entity"
    RELATION = "relation"
    MILESTONE = "milestone"
    RING = "ring"
    BRANCH = "branch"


class MemoryFreshness(str, Enum):
    """Estado de frescura de la Memoria (contrato §6).

    Dimensión propia del bloque, coordinada con **Regar** y con la metáfora del
    jardín; NO fusiona ni sustituye el estado de riego de la entidad. Un
    elemento sano en el jardín puede tener su memoria ``FALTA_REGAR`` si cambió
    un elemento relacionado. Estos estados no cambian el canon.
    """

    SIN_MEMORIA = "sin_memoria"
    REGADA = "regada"
    FALTA_REGAR = "falta_regar"
    SECADA = "secada"


class MemoryOrigin(str, Enum):
    """Origen/autoría de un bloque o cambio de Memoria (contrato §5, §21)."""

    USUARIO = "usuario"
    IA = "ia"
    RIEGO = "riego"
    REGENERACION_MANUAL = "regeneracion_manual"


class MemoryIssueKind(str, Enum):
    """Incidencias editoriales ancladas dentro de la Memoria (contrato §5, §12).

    Se modelan como objetos de primera clase (no texto suelto) para que el motor
    de impacto (MEM-04) y Cultivo (MEM-09) puedan referenciarlas y accionarlas.
    """

    CONTRADICCION = "contradiccion"
    HUECO = "hueco"
    PREGUNTA_ABIERTA = "pregunta_abierta"
    SUPUESTO = "supuesto"


class MemoryIssueStatus(str, Enum):
    """Ciclo de vida de una incidencia (acciones de Cultivo, contrato §12)."""

    ABIERTA = "abierta"
    ACEPTADA = "aceptada"
    CORREGIDA = "corregida"
    APLAZADA = "aplazada"
    IGNORADA = "ignorada"


class MemoryRevisionStatus(str, Enum):
    """Estado de una propuesta de cambio de Memoria (antes/después)."""

    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    SUPERADA = "superada"


# ═══════════════════════════════════════════════════════════════════════
# Parse helpers (tolerantes; el dominio nunca rompe al cargar datos viejos)
# ═══════════════════════════════════════════════════════════════════════


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


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


# ═══════════════════════════════════════════════════════════════════════
# MemoryCitation — fuente/cita hacia canon o referencia estructurada
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MemoryCitation:
    """Fuente/cita hacia un elemento canónico o referencia estructurada.

    Apunta a id/tipo estable (no a texto libre), forward-compat con las
    @menciones estructuradas de MEM-03. ``nota`` es un fragmento opcional para
    depuración y confianza (contrato §5, §9).
    """

    ref_kind: MemoryTargetKind = MemoryTargetKind.ENTITY
    ref_id: str = ""
    nota: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_kind": self.ref_kind.value,
            "ref_id": self.ref_id,
            "nota": self.nota,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCitation:
        return cls(
            ref_kind=_parse_enum(MemoryTargetKind, data.get("ref_kind"), MemoryTargetKind.ENTITY),
            ref_id=_parse_str(data.get("ref_id")),
            nota=_parse_str(data.get("nota")),
        )


def _parse_citation_list(value: Any) -> list[MemoryCitation]:
    if isinstance(value, list):
        return [MemoryCitation.from_dict(item) for item in value if isinstance(item, dict)]
    return []


# ═══════════════════════════════════════════════════════════════════════
# MemoryIssue — contradicción / hueco / pregunta / supuesto anclado
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MemoryIssue:
    """Incidencia editorial de primera clase, anclada a los elementos afectados.

    Una contradicción no modifica canon; queda anclada y accionable en Cultivo
    (contrato §12). MEM-04 la marca/propaga; MEM-09 la muestra y acciona.
    """

    id: str = field(default_factory=lambda: _new_id("memiss"))
    kind: MemoryIssueKind = MemoryIssueKind.CONTRADICCION
    texto: str = ""
    anclado_a: list[MemoryCitation] = field(default_factory=list)
    estado: MemoryIssueStatus = MemoryIssueStatus.ABIERTA
    origin: MemoryOrigin = MemoryOrigin.IA
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "texto": self.texto,
            "anclado_a": [c.to_dict() for c in self.anclado_a],
            "estado": self.estado.value,
            "origin": self.origin.value,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryIssue:
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else _new_id("memiss"),
            kind=_parse_enum(MemoryIssueKind, data.get("kind"), MemoryIssueKind.CONTRADICCION),
            texto=_parse_str(data.get("texto")),
            anclado_a=_parse_citation_list(data.get("anclado_a")),
            estado=_parse_enum(MemoryIssueStatus, data.get("estado"), MemoryIssueStatus.ABIERTA),
            origin=_parse_enum(MemoryOrigin, data.get("origin"), MemoryOrigin.IA),
            created_at=_parse_str(data.get("created_at")) or _now_iso(),
            metadata=_parse_dict(data.get("metadata")),
        )


def _parse_issue_list(value: Any) -> list[MemoryIssue]:
    if isinstance(value, list):
        return [MemoryIssue.from_dict(item) for item in value if isinstance(item, dict)]
    return []


# ═══════════════════════════════════════════════════════════════════════
# MemoryRevisionProposal — propuesta de cambio con antes/después exacto
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MemoryRevisionProposal:
    """Propuesta revisable de cambio de Memoria con snapshot antes/después.

    MEM-02 solo modela y persiste el dato (criterio de aceptación 5). Quién la
    genera (IA/regeneración) y cómo se muestra el diff son MEM-05/07/10. No es
    un candidato de canon: la Memoria no es canon.
    """

    id: str = field(default_factory=lambda: _new_id("memrev"))
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    origin: MemoryOrigin = MemoryOrigin.IA
    motivo: str = ""
    estado: MemoryRevisionStatus = MemoryRevisionStatus.PENDIENTE
    created_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "before": dict(self.before),
            "after": dict(self.after),
            "origin": self.origin.value,
            "motivo": self.motivo,
            "estado": self.estado.value,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRevisionProposal:
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else _new_id("memrev"),
            before=_parse_dict(data.get("before")),
            after=_parse_dict(data.get("after")),
            origin=_parse_enum(MemoryOrigin, data.get("origin"), MemoryOrigin.IA),
            motivo=_parse_str(data.get("motivo")),
            estado=_parse_enum(
                MemoryRevisionStatus, data.get("estado"), MemoryRevisionStatus.PENDIENTE
            ),
            created_at=_parse_str(data.get("created_at")) or _now_iso(),
            metadata=_parse_dict(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════
# NarrativeMemory — el bloque de Memoria (el modelo raíz)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class NarrativeMemory:
    """Bloque de Memoria narrativa derivada, asociado a un elemento por id.

    No duplica el elemento: lo referencia por ``(target_kind, target_id)`` y,
    opcionalmente, un ``context`` para la memoria contextual. Un ``target_id``
    vacío corresponde a la Memoria global de proyecto.
    """

    id: str = field(default_factory=lambda: _new_id("mem"))
    target_kind: MemoryTargetKind = MemoryTargetKind.PROJECT
    target_id: str = ""  # vacío para memoria global de proyecto
    context: str = ""  # descriptor opcional -> memoria contextual
    resumen_editorial: str = ""  # lead / 1-línea que consume el índice de la wiki
    estado_actual: str = ""
    cuerpo: str = ""  # síntesis editorial larga (el "cuerpo" de la página de wiki, BETA2-WIKI-02)
    issues: list[MemoryIssue] = field(default_factory=list)
    notas_causales: list[str] = field(default_factory=list)
    dependencias: list[MemoryCitation] = field(default_factory=list)
    citations: list[MemoryCitation] = field(default_factory=list)
    wikilinks: list[MemoryCitation] = field(default_factory=list)  # enlaces tipados página→elemento
    tags: list[str] = field(default_factory=list)
    freshness: MemoryFreshness = MemoryFreshness.SIN_MEMORIA
    origin: MemoryOrigin = MemoryOrigin.USUARIO
    pending_revision: MemoryRevisionProposal | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def target_key(self) -> tuple[str, str, str]:
        """Clave estable de identidad del bloque (nivel + elemento + contexto)."""
        return (self.target_kind.value, self.target_id, self.context)

    def content_snapshot(self) -> dict[str, Any]:
        """Snapshot de las secciones editoriales (para diff antes/después).

        No incluye ids/timestamps/frescura: solo el contenido que una propuesta
        de revisión podría sustituir.
        """
        return {
            "resumen_editorial": self.resumen_editorial,
            "estado_actual": self.estado_actual,
            "cuerpo": self.cuerpo,
            "issues": [i.to_dict() for i in self.issues],
            "notas_causales": list(self.notas_causales),
            "dependencias": [c.to_dict() for c in self.dependencias],
            "citations": [c.to_dict() for c in self.citations],
            "wikilinks": [c.to_dict() for c in self.wikilinks],
            "tags": list(self.tags),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_kind": self.target_kind.value,
            "target_id": self.target_id,
            "context": self.context,
            "resumen_editorial": self.resumen_editorial,
            "estado_actual": self.estado_actual,
            "cuerpo": self.cuerpo,
            "issues": [i.to_dict() for i in self.issues],
            "notas_causales": list(self.notas_causales),
            "dependencias": [c.to_dict() for c in self.dependencias],
            "citations": [c.to_dict() for c in self.citations],
            "wikilinks": [c.to_dict() for c in self.wikilinks],
            "tags": list(self.tags),
            "freshness": self.freshness.value,
            "origin": self.origin.value,
            "pending_revision": self.pending_revision.to_dict() if self.pending_revision else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NarrativeMemory:
        raw_id = data.get("id")
        raw_revision = data.get("pending_revision")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else _new_id("mem"),
            target_kind=_parse_enum(
                MemoryTargetKind, data.get("target_kind"), MemoryTargetKind.PROJECT
            ),
            target_id=_parse_str(data.get("target_id")),
            context=_parse_str(data.get("context")),
            resumen_editorial=_parse_str(data.get("resumen_editorial")),
            estado_actual=_parse_str(data.get("estado_actual")),
            cuerpo=_parse_str(data.get("cuerpo")),
            issues=_parse_issue_list(data.get("issues")),
            notas_causales=_parse_str_list(data.get("notas_causales")),
            dependencias=_parse_citation_list(data.get("dependencias")),
            citations=_parse_citation_list(data.get("citations")),
            wikilinks=_parse_citation_list(data.get("wikilinks")),
            tags=_parse_str_list(data.get("tags")),
            freshness=_parse_enum(
                MemoryFreshness, data.get("freshness"), MemoryFreshness.SIN_MEMORIA
            ),
            origin=_parse_enum(MemoryOrigin, data.get("origin"), MemoryOrigin.USUARIO),
            pending_revision=(
                MemoryRevisionProposal.from_dict(raw_revision)
                if isinstance(raw_revision, dict)
                else None
            ),
            created_at=_parse_str(data.get("created_at")) or _now_iso(),
            updated_at=_parse_str(data.get("updated_at")) or _now_iso(),
            metadata=_parse_dict(data.get("metadata")),
        )


__all__ = [
    "MemoryCitation",
    "MemoryFreshness",
    "MemoryIssue",
    "MemoryIssueKind",
    "MemoryIssueStatus",
    "MemoryOrigin",
    "MemoryRevisionProposal",
    "MemoryRevisionStatus",
    "MemoryTargetKind",
    "NarrativeMemory",
]
