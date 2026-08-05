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

Reglas de CONTINUIDAD (BETA-MULTIAGENT2-FIX-10, G2-15) — las tres roturas de
sala de guion que el modelo ya podía computar y nadie miraba, más el aviso que
explica el ruido de calendario:
  10. bilocación: un cuerpo (personaje/criatura/objeto) participa el mismo año
      en dos hitos cuyos lugares declarados son disjuntos.
  11. participante fuera de su lapso EN UN HITO (la regla 5 solo miraba la
      relación ``participo_en`` hacia entidades evento/escena/sesión; la
      participación real se modela en ``CausalMilestone.affected_entity_ids``).
  12. conocimiento contradictorio: ``sabe``/``conoce`` conviviendo con
      ``ignora``/``desconoce`` del mismo origen al mismo objeto.
  13. conocimiento anterior a su revelación: la relación de conocimiento nace
      antes del hito de tipo ``revelacion`` que destapa ese objeto.
  14. datación desincronizada: el espejo entero (``birth_year``/``death_year``)
      y el ``life_span`` guardado dicen cosas distintas. No es una incoherencia
      narrativa: es la CAUSA de los avisos de calendario, y sin ella el usuario
      ve síntomas (regla 2) sin poder llegar al origen.

Las reglas 10-14 son funciones aparte, no cuelgan de ``evaluate_entity`` /
``evaluate_relation`` / ``evaluate_milestone``: el camino de aceptación de
candidatos (BETA1-J04) sigue emitiendo exactamente los mismos avisos que antes.
Quien las orquesta sobre el canon COMPLETO es ``continuity_service``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from packages.domain.candidate_issue import Issue, IssueSeverity, IssueType
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneType
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project_chronology import ProjectChronology
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.temporal_models import EventTemporality
from packages.domain.temporal_span import TemporalSpan

# Tipos de entidad que representan un suceso datado puntual (regla 5).
_EVENT_TYPES = frozenset(
    {EntityType.EVENTO, EntityType.ESCENA, EntityType.SESION}
)

# Regla 10: solo un CUERPO puede bilocarse. Una facción, una institución o una
# regla del mundo están en varios sitios a la vez por definición, y avisar de
# ellas sería el ruido que BETA-AUDIT-14 quiso evitar.
_EMBODIED_TYPES = frozenset(
    {EntityType.PERSONAJE, EntityType.CRIATURA, EntityType.OBJETO}
)

# Reglas 12/13: afirmaciones de conocimiento y su negación directa. Estrictas a
# propósito: `cree`, `sospecha`, `ha_oido` o `conoce_parcialmente` NO son
# contradicciones de `ignora` (son medias verdades, que es de lo que vive una
# serie).
_KNOWS_TYPES = frozenset({RelationType.SABE, RelationType.CONOCE})
_IGNORES_TYPES = frozenset({RelationType.IGNORA, RelationType.DESCONOCE})

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


# ── Reglas de continuidad (BETA-MULTIAGENT2-FIX-10) ───────────────────────


def _label_of(entity: NarrativeEntity | None, entity_id: str) -> str:
    if entity is None:
        return entity_id[:8]
    return entity.name or entity.id[:8]


def authoritative_span(entity: NarrativeEntity) -> TemporalSpan:
    """Lapso de la entidad con los años que MANDA el espejo entero.

    ``birth_year``/``death_year`` son, por contrato del dominio (BETA1-J01), el
    espejo entero **autoritativo** de ``life_span``, y son lo que la Ficha le
    enseña al usuario. Cuando los dos discrepan —proyecto editado fuera de los
    servicios, o remapeado a otra escala de años— las reglas nuevas se quedan con
    el espejo: si no, el panel diría «Teo deja de existir en 0» mientras su Ficha
    dice que muere en 1, que es mentirle a la cara. La discrepancia no se esconde:
    la denuncia :func:`evaluate_dating_sync` (T14).

    No muta nada (se llama en lectura); la naturaleza temporal se conserva para
    que sigan valiendo las exenciones de BETA1-J07.
    """
    span = entity.as_temporal_span()
    if span.start_year == entity.birth_year and span.end_year == entity.death_year:
        return span
    return TemporalSpan(
        start=EventTemporality(year=entity.birth_year),
        end=EventTemporality(year=entity.death_year) if entity.death_year is not None else None,
        nature=span.nature,
    )


def _milestone_year(milestone: CausalMilestone) -> int | None:
    return milestone.as_temporal_span().start_year


def _rango(inicio: int | None, fin: int | None) -> str:
    """Un lapso dicho en español, sin ``None`` a la vista del usuario."""
    if inicio is None and fin is None:
        return "sin fechas"
    if fin is None:
        return f"desde {inicio}"
    if inicio is None:
        return f"hasta {fin}"
    return f"{inicio}–{fin}"


def evaluate_bilocation(
    milestones: Sequence[CausalMilestone],
    entities: Mapping[str, NarrativeEntity],
) -> list[TemporalIssue]:
    """T10: un cuerpo en dos hitos del mismo año, en lugares disjuntos.

    **Silencio honesto**: si alguno de los dos hitos no declara ningún
    participante de tipo ``localizacion``, no se sabe dónde pasa y no se juzga.
    Comparte lugar ⇒ tampoco hay bilocación.

    Coste: se agrupa por año primero (los pares solo se miran dentro del grupo),
    nunca el producto cartesiano de todos los hitos.
    """
    por_ano: dict[int, list[tuple[CausalMilestone, set[str], set[str]]]] = {}
    for milestone in milestones:
        year = _milestone_year(milestone)
        if year is None:
            continue
        lugares: set[str] = set()
        cuerpos: set[str] = set()
        for eid in milestone.affected_entity_ids:
            entity = entities.get(eid)
            if entity is None:
                continue
            if entity.entity_type is EntityType.LOCALIZACION:
                lugares.add(eid)
            elif entity.entity_type in _EMBODIED_TYPES:
                # BETA1-J07: un ser eterno/atemporal no está atado a un lugar.
                if not authoritative_span(entity).is_eternal():
                    cuerpos.add(eid)
        if not lugares:
            continue  # el hito no dice dónde pasa: no se inventa
        por_ano.setdefault(year, []).append((milestone, lugares, cuerpos))

    issues: list[TemporalIssue] = []
    for year in sorted(por_ano):
        grupo = por_ano[year]
        for i in range(len(grupo)):
            uno, lugares_uno, cuerpos_uno = grupo[i]
            for j in range(i + 1, len(grupo)):
                otro, lugares_otro, cuerpos_otro = grupo[j]
                if lugares_uno & lugares_otro:
                    continue  # comparten al menos un lugar: puede ser el mismo sitio
                compartidos = sorted(cuerpos_uno & cuerpos_otro)
                if not compartidos:
                    continue
                nombres = ", ".join(
                    f"'{_label_of(entities.get(eid), eid)}'" for eid in compartidos
                )
                sitios_uno = ", ".join(
                    _label_of(entities.get(eid), eid) for eid in sorted(lugares_uno)
                )
                sitios_otro = ", ".join(
                    _label_of(entities.get(eid), eid) for eid in sorted(lugares_otro)
                )
                issues.append(
                    TemporalIssue(
                        code="T10_BILOCATION",
                        message=(
                            f"{nombres} está en dos sitios el mismo año ({year}): "
                            f"'{uno.title or uno.id}' ({sitios_uno}) y "
                            f"'{otro.title or otro.id}' ({sitios_otro})."
                        ),
                        subject_kind="milestone",
                        subject_id=otro.id,
                        related_ids=[uno.id, *compartidos],
                        severity="alta",
                    )
                )
    return issues


def evaluate_milestone_participants(
    milestone: CausalMilestone,
    participants: Iterable[NarrativeEntity],
) -> list[TemporalIssue]:
    """T11: el hito cae fuera de la vida de alguno de sus participantes.

    La regla 5 solo cubría la relación ``participo_en`` hacia una entidad
    evento/escena/sesión; la participación de verdad se declara en
    ``affected_entity_ids`` (lo que la ficha del hito llama «participantes»), y
    ahí no miraba nadie: un muerto podía reaparecer dos temporadas después.

    Exenciones BETA1-J07: un inmortal no deja de existir (no hay «después») y un
    eterno no nace (no hay «antes»). Los años los pone el espejo autoritativo
    (:func:`authoritative_span`), no un lapso que pueda contradecir a la Ficha.
    """
    year = _milestone_year(milestone)
    if year is None:
        return []
    issues: list[TemporalIssue] = []
    titulo = milestone.title or milestone.id
    for entity in participants:
        span = authoritative_span(entity)
        pos = _position(year, span)
        if pos == "after" and span.is_immortal():
            pos = None
        elif pos == "before" and span.is_eternal():
            pos = None
        if pos is None:
            continue
        nombre = entity.name or entity.id
        if pos == "after":
            detalle = (
                f"'{nombre}' participa en el hito '{titulo}' ({year}), pero deja de "
                f"existir en {span.end_year}."
            )
        else:
            detalle = (
                f"'{nombre}' participa en el hito '{titulo}' ({year}), pero no existe "
                f"hasta {span.start_year}."
            )
        issues.append(
            TemporalIssue(
                code="T11_PARTICIPANT_OUTSIDE_LIFE",
                message=detalle,
                subject_kind="milestone",
                subject_id=milestone.id,
                related_ids=[entity.id],
                severity="alta" if pos == "after" else "media",
            )
        )
    return issues


def _spans_overlap(uno: TemporalSpan, otro: TemporalSpan) -> bool:
    """¿Conviven los dos lapsos? Un extremo abierto no acota ese lado."""
    if uno.end_year is not None and otro.start_year is not None and uno.end_year < otro.start_year:
        return False
    if otro.end_year is not None and uno.start_year is not None and otro.end_year < uno.start_year:
        return False
    return True


def evaluate_knowledge(
    relations: Sequence[NarrativeRelation],
    *,
    entities: Mapping[str, NarrativeEntity] | None = None,
    milestones: Sequence[CausalMilestone] | None = None,
) -> list[TemporalIssue]:
    """T12 (contradicción) y T13 (saber anterior a la revelación).

    - **T12** exige que las dos afirmaciones CONVIVAN. Que alguien ignorara algo
      hasta el año 11 y lo sepa después no es una contradicción: es el arco del
      personaje. Sin datar, ambas están vigentes (y esa es la rotura que el
      tester creó a mano).
    - **T13** solo se computa si la relación de conocimiento está DATADA. En el
      mundo entregado las siete relaciones de conocimiento tienen ``birth_year``
      a ``None``: la regla se calla en vez de inventar el dato.

    Indexado por ``(origen, objeto)``: nada de producto cartesiano de relaciones.
    """
    nombres = entities or {}
    por_par: dict[tuple[str, str], list[NarrativeRelation]] = {}
    for relation in relations:
        if relation.relation_type in _KNOWS_TYPES or relation.relation_type in _IGNORES_TYPES:
            por_par.setdefault((relation.source_id, relation.target_id), []).append(relation)

    # Año de la revelación más temprana que destapa cada objeto.
    revelaciones: dict[str, tuple[int, str]] = {}
    for milestone in milestones or []:
        if milestone.milestone_type is not CausalMilestoneType.REVELACION:
            continue
        year = _milestone_year(milestone)
        if year is None:
            continue
        for eid in milestone.affected_entity_ids:
            previa = revelaciones.get(eid)
            if previa is None or year < previa[0]:
                revelaciones[eid] = (year, milestone.title or milestone.id)

    issues: list[TemporalIssue] = []
    for (source_id, target_id), grupo in por_par.items():
        sabe = [r for r in grupo if r.relation_type in _KNOWS_TYPES]
        ignora = [r for r in grupo if r.relation_type in _IGNORES_TYPES]
        quien = _label_of(nombres.get(source_id), source_id)
        que = _label_of(nombres.get(target_id), target_id)
        for relation in sabe:
            contraria = next(
                (
                    otra
                    for otra in ignora
                    if _spans_overlap(relation.as_temporal_span(), otra.as_temporal_span())
                ),
                None,
            )
            if contraria is not None:
                issues.append(
                    TemporalIssue(
                        code="T12_KNOWS_AND_IGNORES",
                        message=(
                            f"'{quien}' {relation.relation_type.value} y "
                            f"{contraria.relation_type.value} '{que}' a la vez."
                        ),
                        subject_kind="relation",
                        subject_id=relation.id,
                        related_ids=[contraria.id, source_id, target_id],
                        severity="alta",
                    )
                )
            revelacion = revelaciones.get(target_id)
            birth = relation.birth_year
            if revelacion is not None and birth is not None and birth < revelacion[0]:
                issues.append(
                    TemporalIssue(
                        code="T13_KNOWS_BEFORE_REVELATION",
                        message=(
                            f"'{quien}' {relation.relation_type.value} '{que}' desde el año "
                            f"{birth}, pero eso se revela en '{revelacion[1]}' "
                            f"({revelacion[0]})."
                        ),
                        subject_kind="relation",
                        subject_id=relation.id,
                        related_ids=[source_id, target_id],
                        severity="alta",
                    )
                )
    return issues


def evaluate_dating_sync(entity: NarrativeEntity) -> list[TemporalIssue]:
    """T14: el espejo entero y el ``life_span`` guardado se contradicen.

    No es una incoherencia de la historia: es la CAUSA de los avisos de
    calendario. ``ensure_life_span`` solo construye el lapso desde el espejo
    cuando falta, así que un proyecto editado fuera de los servicios (o migrado
    a otra escala de años) queda con la Ficha diciendo una cosa y el validador
    leyendo otra. Sin este aviso, el panel enseña N síntomas (regla 2) y ninguna
    causa.
    """
    span = entity.life_span
    if span is None:
        return []  # el lapso se deriva del espejo: no puede discrepar
    if span.start_year == entity.birth_year and span.end_year == entity.death_year:
        return []
    nombre = entity.name or entity.id
    return [
        TemporalIssue(
            code="T14_DATING_DESYNC",
            message=(
                f"{nombre}: la ficha dice «{_rango(entity.birth_year, entity.death_year)}» y "
                f"el lapso guardado dice «{_rango(span.start_year, span.end_year)}»."
            ),
            subject_kind="entity",
            subject_id=entity.id,
            severity="media",
        )
    ]


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
    "authoritative_span",
    "check_calendar",
    "evaluate_bilocation",
    "evaluate_dating_sync",
    "evaluate_entity",
    "evaluate_knowledge",
    "evaluate_milestone",
    "evaluate_milestone_participants",
    "evaluate_relation",
]
