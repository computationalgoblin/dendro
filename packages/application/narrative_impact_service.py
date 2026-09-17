"""NarrativeImpactService — motor de impacto narrativo (BETA2-MEM-04).

Tras un cambio canonico, calcula de forma DETERMINISTA (sin IA) que elementos
dependientes pueden haber quedado con la Memoria obsoleta y los marca
``FALTA_REGAR`` mediante ``NarrativeMemoryService.mark_falta_regar`` — sin borrar
contenido ni tocar canon (contrato memoria_narrativa.md §11, §16).

Diseno cerrado en entrevista (BETA2-MEM-04):
- **Directos + descenso causal**: dependientes directos (relaciones, @menciones
  estructuradas, citas de Memoria) + propagacion DESCENDENTE por anillos; el
  ascenso solo por relacion causal explicita (DEPENDE_DE/CAUSO/...). Sin
  transitividad multi-salto (evita la lista intimidante que proscribe el contrato).
- **Solo marca lo que YA tiene Memoria** (no crea bloques vacios: sin bloat); no
  degrada una Memoria SECADA ni re-marca una ya FALTA_REGAR (idempotente).
- **Disparo uniforme** desde la capa de aplicacion (se invoca tras cada cambio
  canonico), no desde widgets.

El modelo rico de potencia causal (basal/contextual/realizada) y de excepciones
ascendentes (apalancamiento, catalizador, vulnerabilidad) es BETA2-MEM-08.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.application.causal_potency import is_ascending_exception
from packages.application.structured_reference_service import backlinks_for
from packages.application.world_layer_causal import get_causal_rank
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.relation import RelationType
from packages.domain.result import Error, Ok, Result

# Tipos de relacion que expresan dependencia causal explicita: habilitan la
# propagacion ASCENDENTE (un cambio inferior si escala a un superior conectado
# por una de estas relaciones). El resto no escala hacia arriba (contrato §16).
CAUSAL_RELATION_TYPES: frozenset[RelationType] = frozenset(
    {
        RelationType.CAUSO,
        RelationType.FUE_CAUSADO_POR,
        RelationType.DEPENDE_DE,
        RelationType.DERIVA_DE,
        RelationType.CONDICIONA,
        RelationType.EXPLICA,
        RelationType.PRODUCE_CONSECUENCIA_EN,
    }
)


def _as_kind(value: MemoryTargetKind | str) -> MemoryTargetKind:
    if isinstance(value, MemoryTargetKind):
        return value
    return MemoryTargetKind(str(value))


@dataclass(frozen=True)
class ImpactMark:
    """Una marca Falta regar aplicada por el motor (dato explicable)."""

    target_kind: MemoryTargetKind
    target_id: str
    context: str
    via: str  # self | relacion | mencion | cita_memoria | hito
    cause: str


@dataclass
class ImpactResult:
    """Resultado de propagar un cambio: que se marco y cuanto se considero."""

    changed_kind: MemoryTargetKind
    changed_id: str
    marks: list[ImpactMark] = field(default_factory=list)
    considered: int = 0

    def marked_ids(self) -> set[tuple[str, str]]:
        return {(m.target_kind.value, m.target_id) for m in self.marks}


@dataclass
class NarrativeImpactService:
    """Calcula y aplica el impacto de un cambio canonico sobre la Memoria."""

    project_service: object
    memory_service: object = None
    history_service: object = None

    def __post_init__(self) -> None:
        if self.memory_service is None:
            # Import diferido para evitar ciclos y mantener el sink desacoplado.
            from packages.application.narrative_memory_service import NarrativeMemoryService

            self.memory_service = NarrativeMemoryService(self.project_service, self.history_service)

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── API principal ───────────────────────────────────────────────────

    def propagate_change(
        self,
        changed_kind: MemoryTargetKind | str,
        changed_id: str,
        *,
        cause_hint: str = "",
        include_self: bool = True,
        exclude_ids: frozenset[str] | set[str] | None = None,
        only_via: frozenset[str] | set[str] | None = None,
    ) -> Result[ImpactResult, str]:
        """Marca Falta regar las Memorias afectadas por el cambio de un elemento.

        ``include_self=False`` propaga SOLO a los dependientes, no al propio elemento
        (BETA2-WIKI-06): al Regar se acaba de reescribir su página como vigente, así
        que no debe re-marcarse Falta regar a sí mismo; sí sus relacionadas.

        ``exclude_ids`` (BETA-FIX-01, G-01): entidades del MISMO lote de
        riego en curso — sus páginas se reescriben en esta misma autorización; sin
        la exclusión se invalidaban entre sí y un lote de vecinas jamás acababa
        verde (solo la última regada quedaba `regada`).

        ``only_via`` (BETA2-FIX-05, G2-05): restringe la propagación a
        ciertas VÍAS de dependencia (``self``/``mencion``/``cita_memoria``/
        ``relacion``/``hito``). Este motor calcula el impacto de un cambio de CANON;
        Regar NO cambia canon (solo reescribe una página de wiki), así que el camino
        de Regar la restringe a la dependencia REAL — ``mencion`` (alguien @menciona
        al regado) y ``cita_memoria`` (una página lo cita) —, no a la manta
        topológica ``relacion``. Sin esto, regar B degradaba la página vigente de
        cualquier vecina A y dos vecinas no podían estar verdes a la vez fuera de un
        mismo lote (16,5 min de IA con balance neto cero, beta ronda 2, ART-06).
        """
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        kind = _as_kind(changed_kind)
        result = ImpactResult(changed_kind=kind, changed_id=changed_id)
        seen: set[tuple[str, str, str]] = set()
        for target_kind, target_id, context, via, cause in self._candidates(proj, kind, changed_id):
            if not target_id:
                continue
            if via == "self" and not include_self:
                continue
            if only_via is not None and via not in only_via:
                continue  # FIX-05: solo dependencia real (ver docstring)
            if (
                exclude_ids
                and target_kind is MemoryTargetKind.ENTITY
                and target_id in exclude_ids
            ):
                continue
            key = (target_kind.value, target_id, context)
            if key in seen:
                continue
            seen.add(key)
            result.considered += 1
            full_cause = f"{cause_hint} — {cause}" if cause_hint else cause
            if self._mark(target_kind, target_id, context, full_cause):
                result.marks.append(ImpactMark(target_kind, target_id, context, via, full_cause))
        return Ok(result)

    def preview_entity_dependents(
        self, entity_id: str, *, at_rank: int | None = None
    ) -> list[tuple[MemoryTargetKind, str, str]]:
        """Dry-run READ-ONLY de dependientes de una entidad por dirección de anillo,
        SIN marcar Memoria (BETA2-STRUCT-01).

        Reutiliza la MISMA regla de propagación que ``_relation_dependents``
        (descendente/lateral automático; ascendente solo si la relación es causal o
        excepción ascendente), pero no escribe nada. ``at_rank`` permite simular el
        resultado si la entidad estuviera en un anillo de rank distinto (para estimar
        las consecuencias de MOVERLA). Devuelve (kind, id, causa) de los dependientes
        ENTIDAD, deduplicados. Es la primitiva de "consecuencias esperadas" §17.
        """
        proj = self._proj()
        if proj is None or not hasattr(proj, "relations_for"):
            return []
        rank_map = self._layer_rank_map(proj)
        if at_rank is not None:
            changed_rank = at_rank
        else:
            changed_rank = self._entity_rank(proj, entity_id, rank_map)
        out: list[tuple[MemoryTargetKind, str, str]] = []
        seen: set[str] = set()
        for rel in proj.relations_for(entity_id):
            neighbor = rel.target_id if rel.source_id == entity_id else rel.source_id
            if not neighbor or neighbor == entity_id or neighbor in seen:
                continue
            neighbor_rank = self._entity_rank(proj, neighbor, rank_map)
            causal = rel.relation_type in CAUSAL_RELATION_TYPES or is_ascending_exception(rel)
            if self._propagates(changed_rank, neighbor_rank, causal):
                seen.add(neighbor)
                out.append(
                    (MemoryTargetKind.ENTITY, neighbor, "dependiente por dirección de anillo")
                )
        return out

    # ── calculo del conjunto afectado (determinista) ────────────────────

    def _candidates(self, proj, kind: MemoryTargetKind, changed_id: str):
        cands: list[tuple[MemoryTargetKind, str, str, str, str]] = []
        # El propio elemento: su Memoria queda potencialmente obsoleta.
        cands.append((kind, changed_id, "", "self", "el elemento cambio"))
        # @menciones estructuradas: quien menciona al elemento que cambio.
        for ref in backlinks_for(proj, kind, changed_id):
            cands.append(
                (ref.source_kind, ref.source_id, "", "mencion", "menciona un elemento que cambio")
            )
        # Citas de Memoria: bloques cuya dependencia/cita apunta al elemento.
        for block in getattr(proj, "narrative_memories", []) or []:
            if self._block_cites(block, kind, changed_id):
                cands.append(
                    (
                        block.target_kind,
                        block.target_id,
                        block.context,
                        "cita_memoria",
                        "la Memoria cita un elemento que cambio",
                    )
                )
        # Senales estructurales por tipo de elemento.
        if kind == MemoryTargetKind.ENTITY:
            cands.extend(self._relation_dependents(proj, changed_id))
        elif kind == MemoryTargetKind.RELATION:
            rel = proj.relation_by_id(changed_id) if hasattr(proj, "relation_by_id") else None
            if rel is not None:
                for eid in (rel.source_id, rel.target_id):
                    cands.append(
                        (MemoryTargetKind.ENTITY, eid, "", "relacion", "cambio una relacion suya")
                    )
        elif kind == MemoryTargetKind.MILESTONE:
            cands.extend(self._milestone_dependents(proj, changed_id))
        return cands

    def _relation_dependents(self, proj, entity_id: str):
        out: list[tuple[MemoryTargetKind, str, str, str, str]] = []
        if not hasattr(proj, "relations_for"):
            return out
        rank_map = self._layer_rank_map(proj)
        changed_rank = self._entity_rank(proj, entity_id, rank_map)
        for rel in proj.relations_for(entity_id):
            neighbor = rel.target_id if rel.source_id == entity_id else rel.source_id
            # La propia relacion depende de sus extremos.
            out.append(
                (MemoryTargetKind.RELATION, rel.id, "", "relacion", "cambio una entidad suya")
            )
            if not neighbor:
                continue
            neighbor_rank = self._entity_rank(proj, neighbor, rank_map)
            # BETA2-MEM-08: el ascenso lo habilita un tipo causal explicito O una
            # excepcion ascendente marcada (apalancamiento/catalizador/vulnerabilidad…).
            causal = rel.relation_type in CAUSAL_RELATION_TYPES or is_ascending_exception(rel)
            if self._propagates(changed_rank, neighbor_rank, causal):
                out.append(
                    (
                        MemoryTargetKind.ENTITY,
                        neighbor,
                        "",
                        "relacion",
                        "relacionado con un elemento que cambio",
                    )
                )
        return out

    def _milestone_dependents(self, proj, milestone_id: str):
        out: list[tuple[MemoryTargetKind, str, str, str, str]] = []
        hitos = getattr(proj, "causal_milestones", []) or []
        changed = next((h for h in hitos if h.id == milestone_id), None)
        if changed is None:
            return out
        for eid in getattr(changed, "affected_entity_ids", []) or []:
            out.append(
                (MemoryTargetKind.ENTITY, eid, "", "hito", "afectado por un hito que cambio")
            )
        for h in hitos:
            if milestone_id in (getattr(h, "causal_parent_hito_ids", []) or []):
                out.append(
                    (
                        MemoryTargetKind.MILESTONE,
                        h.id,
                        "",
                        "hito",
                        "consecuencia causal de un hito que cambio",
                    )
                )
            if getattr(h, "parent_milestone_id", None) == milestone_id:
                out.append(
                    (MemoryTargetKind.MILESTONE, h.id, "", "hito", "subhito de un hito que cambio")
                )
        return out

    # ── direccionalidad causal por anillos ──────────────────────────────

    @staticmethod
    def _propagates(changed_rank, neighbor_rank, causal: bool) -> bool:
        """Descendente/lateral = automatico; ascendente = solo si es causal."""
        if changed_rank is None or neighbor_rank is None:
            return True  # direccion desconocida -> lateral, propaga
        if neighbor_rank >= changed_rank:
            return True  # mismo o inferior (rank mayor) -> descendente/lateral
        return causal  # vecino superior -> solo con relacion causal explicita

    @staticmethod
    def _layer_rank_map(proj) -> dict[str, int]:
        out: dict[str, int] = {}
        for layer in getattr(proj, "world_layers", []) or []:
            rank = get_causal_rank(layer)
            if rank is not None:
                out[layer.id] = rank
        return out

    @staticmethod
    def _entity_rank(proj, entity_id: str, rank_map: dict[str, int]):
        entity = proj.entity_by_id(entity_id) if hasattr(proj, "entity_by_id") else None
        if entity is None:
            return None
        ranks = [
            rank_map[lid] for lid in (getattr(entity, "layer_ids", []) or []) if lid in rank_map
        ]
        return min(ranks) if ranks else None  # min rank = anillo mas aguas arriba

    # ── citas de Memoria ────────────────────────────────────────────────

    @staticmethod
    def _block_cites(block, kind: MemoryTargetKind, target_id: str) -> bool:
        def _hits(citations) -> bool:
            return any(c.ref_kind == kind and c.ref_id == target_id for c in (citations or []))

        if _hits(getattr(block, "dependencias", [])) or _hits(getattr(block, "citations", [])):
            return True
        return any(
            _hits(getattr(issue, "anclado_a", [])) for issue in getattr(block, "issues", []) or []
        )

    # ── marcado (respetando estados de frescura) ────────────────────────

    def _mark(self, kind: MemoryTargetKind, target_id: str, context: str, cause: str) -> bool:
        got = self.memory_service.get_memory(kind, target_id, context)
        block = got.value if isinstance(got, Ok) else None
        if block is None:
            return False  # sin Memoria -> no crear (decision 2)
        if block.freshness != MemoryFreshness.REGADA:
            return False  # solo REGADA -> FALTA_REGAR (idempotente, no degrada SECADA)
        res = self.memory_service.mark_falta_regar(
            kind, target_id, context, causa=cause, change_origin="impacto", create_if_missing=False
        )
        return isinstance(res, Ok) and res.value is not None


__all__ = ["CAUSAL_RELATION_TYPES", "ImpactMark", "ImpactResult", "NarrativeImpactService"]
