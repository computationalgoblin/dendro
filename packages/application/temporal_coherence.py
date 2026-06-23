"""Validador determinista de coherencia temporal — BETA1-J02.

Funciones **puras** (sin I/O ni estado) que, dada una creación narrativa
(hoja/rama, relación o hito) y su contexto de **vecinos directos** ya
resuelto, devuelven una lista de ``TemporalIssue`` (avisos blandos). NO es la
IA: es lógica de dominio determinista. NO bloquea — el flujo de candidatos
decide (BETA1-J04).

Reglas v1 (calendario + vecinos directos):
  1. ``start.year <= end.year``.
  2. inicio/fin dentro de una era válida del proyecto.
  3. coherencia con ``present_year`` (no nacer después del presente).
  4. relación dentro de la vida de sus dos extremos.
  5. evento/escena dentro de la vida de sus participantes.
  6. padre (contenedor) antes que hijo (contenido).
  7. hito hijo causal posterior al hito padre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.domain.candidate_issue import Issue, IssueSeverity, IssueType
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project_chronology import ProjectChronology
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.temporal_span import TemporalSpan

# Tipos de entidad que representan un suceso datado puntual (regla 5).
_EVENT_TYPES = frozenset(
    {EntityType.EVENTO, EntityType.ESCENA, EntityType.SESION}
)

_SEVERITY_MAP = {
    "alta": IssueSeverity.ALTA,
    "media": IssueSeverity.MEDIA,
    "baja": IssueSeverity.BAJA,
}


@dataclass
class TemporalIssue:
    """Aviso de incoherencia temporal (blando)."""

    code: str
    message: str
    subject_kind: str  # "entity" | "relation" | "milestone"
    subject_id: str
    related_ids: list[str] = field(default_factory=list)
    severity: str = "media"

    def to_issue(self) -> Issue:
        """Mapea a un ``Issue`` de dominio (pregunta abierta / advertencia)."""
        return Issue(
            issue_type=IssueType.ADVERTENCIA,
            severity=_SEVERITY_MAP.get(self.severity, IssueSeverity.MEDIA),
            title=self.code,
            description=self.message,
            affected_entity_id=self.subject_id if self.subject_kind == "entity" else None,
            affected_relation_id=self.subject_id if self.subject_kind == "relation" else None,
            metadata={"code": self.code, "related_ids": list(self.related_ids)},
        )


# ── Primitivas ────────────────────────────────────────────────────────────


def _position(year: int | None, span: TemporalSpan) -> str | None:
    """¿Dónde cae *year* respecto a *span*? 'before' / 'after' / None (dentro
    o indeterminable)."""
    if year is None:
        return None
    s = span.start_year
    if s is not None and year < s:
        return "before"
    e = span.end_year
    if e is not None and year > e:
        return "after"
    return None


def check_calendar(
    span: TemporalSpan,
    chronology: ProjectChronology | None,
    *,
    kind: str,
    subject_id: str,
    label: str = "",
) -> list[TemporalIssue]:
    """Reglas 1-3 sobre un lapso aislado."""
    issues: list[TemporalIssue] = []
    start = span.start_year
    end = span.end_year
    name = label or subject_id

    # Regla 1: fin antes que inicio.
    if start is not None and end is not None and end < start:
        issues.append(
            TemporalIssue(
                code="T01_END_BEFORE_START",
                message=f"{name}: el año de fin ({end}) es anterior al de inicio ({start}).",
                subject_kind=kind,
                subject_id=subject_id,
                severity="alta",
            )
        )

    if chronology is not None:
        # Regla 2: año fuera de las eras definidas.
        if chronology.eras:
            for year, which in ((start, "inicio"), (end, "fin")):
                if year is not None and chronology.era_for_year(year) is None:
                    issues.append(
                        TemporalIssue(
                            code="T02_OUTSIDE_ERAS",
                            message=(
                                f"{name}: el año de {which} ({year}) no cae en ninguna era "
                                "del calendario."
                            ),
                            subject_kind=kind,
                            subject_id=subject_id,
                            severity="media",
                        )
                    )
        # Regla 3: nacer después del presente.
        if start is not None and start > chronology.present_year:
            issues.append(
                TemporalIssue(
                    code="T03_START_AFTER_PRESENT",
                    message=(
                        f"{name}: el año de inicio ({start}) es posterior al presente "
                        f"({chronology.present_year})."
                    ),
                    subject_kind=kind,
                    subject_id=subject_id,
                    severity="baja",
                )
            )
    return issues


# ── Evaluadores por tipo ──────────────────────────────────────────────────


def evaluate_entity(
    entity: NarrativeEntity,
    *,
    chronology: ProjectChronology | None = None,
) -> list[TemporalIssue]:
    """Reglas de calendario sobre la hoja/rama (1-3)."""
    span = entity.as_temporal_span()
    label = entity.name or entity.id
    issues = check_calendar(
        span, chronology, kind="entity", subject_id=entity.id, label=label
    )
    issues += _check_nature(span, kind="entity", subject_id=entity.id, label=label)
    return issues


def _check_nature(
    span: TemporalSpan, *, kind: str, subject_id: str, label: str
) -> list[TemporalIssue]:
    """BETA1-J07: coherencia entre la naturaleza temporal y las fechas."""
    issues: list[TemporalIssue] = []
    # T08: un inmortal/eterno no debería tener año de muerte.
    if span.is_immortal() and span.end_year is not None:
        issues.append(
            TemporalIssue(
                code="T08_IMMORTAL_WITH_DEATH",
                message=(
                    f"{label}: es un ser inmortal ({span.nature.value}) pero tiene año de "
                    f"muerte ({span.end_year})."
                ),
                subject_kind=kind,
                subject_id=subject_id,
                severity="media",
            )
        )
    # T09: un eterno/atemporal no debería tener un nacimiento mortal concreto.
    if span.is_eternal() and span.start_year is not None:
        issues.append(
            TemporalIssue(
                code="T09_ETERNAL_WITH_FINITE_BIRTH",
                message=(
                    f"{label}: es un ser eterno ({span.nature.value}) pero tiene un año de "
                    f"nacimiento concreto ({span.start_year}); su origen debería ser primordial."
                ),
                subject_kind=kind,
                subject_id=subject_id,
                severity="media",
            )
        )
    return issues


def evaluate_relation(
    relation: NarrativeRelation,
    *,
    source: NarrativeEntity | None = None,
    target: NarrativeEntity | None = None,
    chronology: ProjectChronology | None = None,
) -> list[TemporalIssue]:
    """Calendario (1-3) + vecinos directos (4, 5, 6)."""
    span = relation.as_temporal_span()
    issues = check_calendar(
        span,
        chronology,
        kind="relation",
        subject_id=relation.id,
        label=f"relación {relation.relation_type.value}",
    )
    start = span.start_year

    # Regla 4: la relación no puede existir fuera de la vida de cada extremo.
    for end_entity, role in ((source, "origen"), (target, "destino")):
        if end_entity is None:
            continue
        end_span = end_entity.as_temporal_span()
        pos = _position(start, end_span)
        # BETA1-J07: exención de falsos positivos con seres inmortales/eternos:
        # un inmortal no "muere" (no hay 'después'); un eterno no "nace" (no hay
        # 'antes'). Su lapso es abierto por naturaleza.
        if pos == "after" and end_span.is_immortal():
            pos = None
        elif pos == "before" and end_span.is_eternal():
            pos = None
        if pos == "before":
            issues.append(
                TemporalIssue(
                    code="T04_RELATION_BEFORE_ENDPOINT",
                    message=(
                        f"La relación empieza ({start}) antes de que exista su {role} "
                        f"'{end_entity.name or end_entity.id}'."
                    ),
                    subject_kind="relation",
                    subject_id=relation.id,
                    related_ids=[end_entity.id],
                    severity="alta",
                )
            )
        elif pos == "after":
            issues.append(
                TemporalIssue(
                    code="T04_RELATION_AFTER_ENDPOINT",
                    message=(
                        f"La relación empieza ({start}) después de que su {role} "
                        f"'{end_entity.name or end_entity.id}' deje de existir."
                    ),
                    subject_kind="relation",
                    subject_id=relation.id,
                    related_ids=[end_entity.id],
                    severity="alta",
                )
            )

    # Regla 5: participación en un evento → el evento cae en la vida del participante.
    if (
        relation.relation_type is RelationType.PARTICIPO_EN
        and source is not None
        and target is not None
        and target.entity_type in _EVENT_TYPES
    ):
        event_year = target.as_temporal_span().start_year
        if _position(event_year, source.as_temporal_span()) is not None:
            issues.append(
                TemporalIssue(
                    code="T05_EVENT_OUTSIDE_PARTICIPANT_LIFE",
                    message=(
                        f"El evento '{target.name or target.id}' ({event_year}) cae fuera de la "
                        f"vida del participante '{source.name or source.id}'."
                    ),
                    subject_kind="relation",
                    subject_id=relation.id,
                    related_ids=[source.id, target.id],
                    severity="media",
                )
            )

    # Regla 6: contenedor/padre antes que contenido/hijo.
    parent, child = _parent_child(relation, source, target)
    if parent is not None and child is not None:
        py = parent.as_temporal_span().start_year
        cy = child.as_temporal_span().start_year
        if py is not None and cy is not None and cy < py:
            issues.append(
                TemporalIssue(
                    code="T06_CHILD_BEFORE_PARENT",
                    message=(
                        f"'{child.name or child.id}' ({cy}) empieza antes que su contenedor "
                        f"'{parent.name or parent.id}' ({py})."
                    ),
                    subject_kind="relation",
                    subject_id=relation.id,
                    related_ids=[parent.id, child.id],
                    severity="media",
                )
            )
    return issues


def evaluate_milestone(
    milestone: CausalMilestone,
    *,
    parent_milestones: list[CausalMilestone] | None = None,
    chronology: ProjectChronology | None = None,
) -> list[TemporalIssue]:
    """Calendario (1-3) + hito hijo posterior a sus padres (7)."""
    span = milestone.as_temporal_span()
    issues = check_calendar(
        span,
        chronology,
        kind="milestone",
        subject_id=milestone.id,
        label=f"hito '{milestone.title or milestone.id}'",
    )
    child_year = span.start_year
    for parent in parent_milestones or []:
        parent_year = parent.as_temporal_span().start_year
        if child_year is not None and parent_year is not None and child_year < parent_year:
            issues.append(
                TemporalIssue(
                    code="T07_MILESTONE_BEFORE_PARENT",
                    message=(
                        f"El hito '{milestone.title or milestone.id}' ({child_year}) es anterior "
                        f"a su hito causal padre '{parent.title or parent.id}' ({parent_year})."
                    ),
                    subject_kind="milestone",
                    subject_id=milestone.id,
                    related_ids=[parent.id],
                    severity="alta",
                )
            )
    return issues


# ── Helpers ────────────────────────────────────────────────────────────────

# Relaciones de contención/pertenencia: (parent_es_origen).
_CONTAINER_AS_SOURCE = frozenset({RelationType.CONTIENE, RelationType.GOBIERNA})
_CONTAINER_AS_TARGET = frozenset({RelationType.PERTENECE_A, RelationType.ESTA_UBICADO_EN})


def _parent_child(
    relation: NarrativeRelation,
    source: NarrativeEntity | None,
    target: NarrativeEntity | None,
) -> tuple[NarrativeEntity | None, NarrativeEntity | None]:
    """Devuelve (padre, hijo) según el tipo de relación de contención, o
    (None, None) si la relación no es de contención."""
    if relation.relation_type in _CONTAINER_AS_SOURCE:
        return source, target
    if relation.relation_type in _CONTAINER_AS_TARGET:
        return target, source
    return None, None


__all__ = [
    "TemporalIssue",
    "check_calendar",
    "evaluate_entity",
    "evaluate_relation",
    "evaluate_milestone",
]
