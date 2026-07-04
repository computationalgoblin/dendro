"""Clasificador de zonas del Modo Foco: Raíces / Entorno / Brotes (BETA2-FOCO).

Dado un proyecto y una entidad central, clasifica de forma determinista a sus
vecinas en las tres zonas del escritorio de Foco. Lo consumen la UI (layout del
lienzo, navegación por flechas) y el contexto compacto del riego.

Heurística combinada (decisión de producto BETA2-FOCO, en orden de prioridad):

1. Familia causal dirigida: quien causa/condiciona/explica al centro ⇒ Raíces;
   lo que el centro causa/deriva ⇒ Brotes. Señales contradictorias ⇒ Entorno.
2. Contención: la rama contenedora del centro NO es un satélite — se devuelve
   aparte (``classify_containers``, cadena con la inmediata primero) y la UI
   la dibuja como MARCO envolvente del centro (BETA2-FOCO-22); los hijos
   contenidos ⇒ Brotes.
3. Anillos: rango causal de capas (``world_layer_causal``) — anillo superior ⇒
   Raíces, inferior ⇒ Brotes.
4. Hitos: co-afectadas por un hito fechado antes del centro ⇒ Raíces; después ⇒
   Brotes. ``classify_milestones`` clasifica los hitos mismos para la UI.
5. Sin señal ⇒ Entorno.

Las zonas NO son "causas/consecuencias" estrictas: Raíces = contexto que hace
verosímil a la entidad; Brotes = derivaciones/desarrollos que nacen de ella.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from packages.application.world_layer_causal import is_causally_above
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.world_layer import WorldLayer


class CausalZone(str, Enum):
    """Zonas del escritorio de Foco."""

    RAICES = "raices"
    ENTORNO = "entorno"
    BROTES = "brotes"


@dataclass(frozen=True)
class ZonedNeighbor:
    """Vecina clasificada. ``relation_id`` vacío = vínculo por hito, no por relación."""

    entity_id: str
    relation_id: str
    zone: str
    reason: str  # causal | child | container | causal_rank | milestone | conflicting | default
    is_ghost: bool


# El origen (source) de estos tipos actúa como CAUSA/SOSTÉN del destino.
_CAUSE_AS_SOURCE = frozenset(
    {
        RelationType.CAUSO,
        RelationType.CONDICIONA,
        RelationType.EXPLICA,
        RelationType.PRODUCE_CONSECUENCIA_EN,
    }
)

# El origen de estos tipos actúa como EFECTO/DERIVADO del destino.
_EFFECT_AS_SOURCE = frozenset(
    {
        RelationType.FUE_CAUSADO_POR,
        RelationType.DERIVA_DE,
        RelationType.DEPENDE_DE,
    }
)

# Estados de canon que no participan del jardín activo.
_EXCLUDED_CANON = frozenset({CanonState.ARCHIVADO, CanonState.DESCARTADO})

# Prioridad de señal al agregar varias relaciones sobre el mismo par.
_REASON_PRIORITY = {"causal": 3, "child": 2, "container": 2, "causal_rank": 1, "milestone": 1}

# Hitos que no cuentan para las zonas.
_EXCLUDED_MILESTONE_STATUS = frozenset(
    {CausalMilestoneStatus.REJECTED, CausalMilestoneStatus.ARCHIVED}
)


def is_ghost_entity(entity: NarrativeEntity | None) -> bool:
    """True si la entidad es un nodo fantasma (placeholder manual no-canon)."""
    return entity is not None and entity.canon_state == CanonState.FANTASMA


def _relation_signal(relation: NarrativeRelation, center_id: str) -> tuple[str, str] | None:
    """Zona sugerida por UNA relación para la vecina del centro, o None."""
    relation_type = relation.relation_type
    outgoing = relation.source_id == center_id
    if relation_type in _CAUSE_AS_SOURCE:
        return (CausalZone.BROTES.value if outgoing else CausalZone.RAICES.value, "causal")
    if relation_type in _EFFECT_AS_SOURCE:
        return (CausalZone.RAICES.value if outgoing else CausalZone.BROTES.value, "causal")
    if relation_type == RelationType.CONTIENE:
        # centro contiene X ⇒ X es hija (brote); X contiene al centro ⇒ X es su rama (entorno).
        return (
            (CausalZone.BROTES.value, "child")
            if outgoing
            else (CausalZone.ENTORNO.value, "container")
        )
    if relation_type == RelationType.PERTENECE_A:
        return (
            (CausalZone.ENTORNO.value, "container")
            if outgoing
            else (CausalZone.BROTES.value, "child")
        )
    return None


def _first_layer(
    entity: NarrativeEntity | None, layers_by_id: dict[str, WorldLayer]
) -> WorldLayer | None:
    if entity is None:
        return None
    for layer_id in entity.layer_ids or []:
        layer = layers_by_id.get(layer_id)
        if layer is not None:
            return layer
    return None


def _center_year(center: NarrativeEntity) -> int | None:
    return center.birth_year


def _milestone_year(milestone: CausalMilestone) -> int | None:
    if milestone.year is not None:
        return milestone.year
    span = milestone.as_temporal_span()
    return getattr(span, "start_year", None)


def _milestone_zone(milestone: CausalMilestone, center_year: int | None) -> str:
    year = _milestone_year(milestone)
    if year is None or center_year is None:
        return CausalZone.ENTORNO.value
    # Un hito del mismo año que el nacimiento arraiga (evento fundacional).
    if year <= center_year:
        return CausalZone.RAICES.value
    return CausalZone.BROTES.value


def _empty_zones() -> dict[str, list[ZonedNeighbor]]:
    return {zone.value: [] for zone in CausalZone}


def classify_neighbors(project: Project, entity_id: str) -> dict[str, list[ZonedNeighbor]]:
    """Clasifica a las vecinas directas del centro en Raíces/Entorno/Brotes.

    Determinista: dentro de cada zona el orden es por nombre (y a igualdad,
    por id). Devuelve siempre las tres claves, con listas posiblemente vacías.
    """
    zones = _empty_zones()
    center = project.entity_by_id(entity_id)
    if center is None:
        return zones

    layers_by_id = {layer.id: layer for layer in project.world_layers}
    center_layer = _first_layer(center, layers_by_id)

    # 1-2) Señales por relación, agregadas por vecina con prioridad y conflicto.
    # signals: neighbor_id -> (zone, reason, priority, relation_id, conflicting)
    signals: dict[str, tuple[str, str, int, str]] = {}
    conflicted: set[str] = set()
    neighbor_relations: dict[str, str] = {}
    for relation in project.relations_for(entity_id):
        other_id = relation.target_id if relation.source_id == entity_id else relation.source_id
        if other_id == entity_id:
            continue
        other = project.entity_by_id(other_id)
        if other is None or other.canon_state in _EXCLUDED_CANON:
            continue
        neighbor_relations.setdefault(other_id, relation.id)
        signal = _relation_signal(relation, entity_id)
        if signal is None:
            continue
        zone, reason = signal
        priority = _REASON_PRIORITY.get(reason, 0)
        previous = signals.get(other_id)
        if previous is None or priority > previous[2]:
            signals[other_id] = (zone, reason, priority, relation.id)
            conflicted.discard(other_id)
        elif priority == previous[2] and zone != previous[0]:
            conflicted.add(other_id)

    classified: dict[str, ZonedNeighbor] = {}
    container_ids: set[str] = set()
    for other_id, relation_id in neighbor_relations.items():
        other = project.entity_by_id(other_id)
        ghost = is_ghost_entity(other)
        # BETA2-FOCO-22: la contenedora directa NO es un satélite — la UI la
        # dibuja como marco envolvente (classify_containers la expone aparte).
        signal = signals.get(other_id)
        if signal is not None and signal[1] == "container" and other_id not in conflicted:
            container_ids.add(other_id)
            continue
        if other_id in conflicted:
            classified[other_id] = ZonedNeighbor(
                other_id, signals[other_id][3], CausalZone.ENTORNO.value, "conflicting", ghost
            )
            continue
        signal = signals.get(other_id)
        if signal is not None:
            zone, reason, _, signal_relation_id = signal
            classified[other_id] = ZonedNeighbor(other_id, signal_relation_id, zone, reason, ghost)
            continue
        # 3) Sin señal de relación: rango causal de anillos.
        other_layer = _first_layer(other, layers_by_id)
        if center_layer is not None and other_layer is not None:
            if is_causally_above(other_layer, center_layer):
                classified[other_id] = ZonedNeighbor(
                    other_id, relation_id, CausalZone.RAICES.value, "causal_rank", ghost
                )
                continue
            if is_causally_above(center_layer, other_layer):
                classified[other_id] = ZonedNeighbor(
                    other_id, relation_id, CausalZone.BROTES.value, "causal_rank", ghost
                )
                continue
        # 5) Sin señal ⇒ Entorno.
        classified[other_id] = ZonedNeighbor(
            other_id, relation_id, CausalZone.ENTORNO.value, "default", ghost
        )

    # 4) Co-afectadas por hitos fechados (solo si no llegaron ya por relación).
    center_year = _center_year(center)
    for milestone in project.causal_milestones:
        if milestone.status in _EXCLUDED_MILESTONE_STATUS:
            continue
        if entity_id not in milestone.affected_entity_ids:
            continue
        zone = _milestone_zone(milestone, center_year)
        for other_id in milestone.affected_entity_ids:
            if other_id == entity_id or other_id in classified:
                continue
            if other_id in container_ids:
                # FOCO-22: la contenedora es marco, no vuelve como satélite.
                continue
            other = project.entity_by_id(other_id)
            if other is None or other.canon_state in _EXCLUDED_CANON:
                continue
            classified[other_id] = ZonedNeighbor(
                other_id, "", zone, "milestone", is_ghost_entity(other)
            )

    def _sort_key(neighbor: ZonedNeighbor) -> tuple[str, str]:
        entity = project.entity_by_id(neighbor.entity_id)
        name = entity.name if entity is not None else ""
        return (name.casefold(), neighbor.entity_id)

    for neighbor in classified.values():
        zones[neighbor.zone].append(neighbor)
    for zone_list in zones.values():
        zone_list.sort(key=_sort_key)
    return zones


def _direct_containers(project: Project, entity_id: str) -> list[tuple[str, str]]:
    """[(container_id, relation_id)] de las contenedoras DIRECTAS, orden por nombre."""
    found: dict[str, str] = {}
    for relation in project.relations_for(entity_id):
        other_id = relation.target_id if relation.source_id == entity_id else relation.source_id
        if other_id == entity_id:
            continue
        other = project.entity_by_id(other_id)
        if other is None or other.canon_state in _EXCLUDED_CANON:
            continue
        signal = _relation_signal(relation, entity_id)
        if signal is not None and signal[1] == "container":
            found.setdefault(other_id, relation.id)

    def _name_key(item: tuple[str, str]) -> tuple[str, str]:
        entity = project.entity_by_id(item[0])
        return ((entity.name if entity else "").casefold(), item[0])

    return sorted(found.items(), key=_name_key)


def classify_containers(project: Project, entity_id: str) -> list[ZonedNeighbor]:
    """Cadena de contención del centro, la INMEDIATA primero (BETA2-FOCO-22).

    La primera entrada es la rama contenedora directa (si hay varias, la
    primera por nombre; el resto se añade tras ella en el mismo nivel); a
    continuación, las ancestras siguiendo la primera contenedora de cada
    nivel. Sin ciclos y con tope defensivo de profundidad.
    """
    chain: list[ZonedNeighbor] = []
    seen: set[str] = {entity_id}
    level = _direct_containers(project, entity_id)
    depth = 0
    while level and depth < 6:
        next_anchor = ""
        for container_id, relation_id in level:
            if container_id in seen:
                continue
            seen.add(container_id)
            container = project.entity_by_id(container_id)
            chain.append(
                ZonedNeighbor(
                    container_id,
                    relation_id,
                    CausalZone.ENTORNO.value,
                    "container",
                    is_ghost_entity(container),
                )
            )
            if not next_anchor:
                next_anchor = container_id
        if not next_anchor:
            break
        level = _direct_containers(project, next_anchor)
        depth += 1
    return chain


def classify_milestones(project: Project, entity_id: str) -> dict[str, list[str]]:
    """Clasifica los hitos que afectan al centro (ids por zona, orden por año/título).

    Año ≤ nacimiento del centro ⇒ Raíces (contexto fundacional); posterior ⇒
    Brotes; sin años comparables ⇒ Entorno (la banda de cronología local los
    muestra igualmente).
    """
    zones: dict[str, list[str]] = {zone.value: [] for zone in CausalZone}
    center = project.entity_by_id(entity_id)
    if center is None:
        return zones
    center_year = _center_year(center)

    dated: list[tuple[int | None, str, str, str]] = []
    for milestone in project.causal_milestones:
        if milestone.status in _EXCLUDED_MILESTONE_STATUS:
            continue
        if entity_id not in milestone.affected_entity_ids:
            continue
        zone = _milestone_zone(milestone, center_year)
        year = _milestone_year(milestone)
        dated.append((year, milestone.title.casefold(), milestone.id, zone))

    dated.sort(key=lambda item: (item[0] is None, item[0] if item[0] is not None else 0, item[1]))
    for _, _, milestone_id, zone in dated:
        zones[zone].append(milestone_id)
    return zones
