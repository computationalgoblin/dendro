"""Continuidad: el validador temporal corriendo sobre TODO el canon del autor.

BETA2-FIX-10 (G2-15). El motor determinista de BETA1-J02
(``temporal_coherence``) existía, era puro y tenía **un solo llamador de
producto**: ``CandidateService.accept_candidate``. Es decir, la app vigilaba lo
que propone la IA y no vigilaba lo que escribe el autor —justo al revés de como
trabaja un jefe de continuidad, que escribe él los episodios—.

Este servicio es el orquestador que faltaba:

- **Determinista y de coste IA CERO.** No importa ``infrastructure``, no llama a
  ningún proveedor y funciona con la IA apagada. La Continuidad es temporal y
  causal de principio a fin.
- **Derive-on-read**, cacheado por ``(project.id, project._index_revision)``, el
  mismo patrón que ``structural_analysis_service``. No persiste ni un hallazgo:
  solo las DECISIONES del usuario (descartes) viven en
  ``custom_metadata``/``metadata`` — append-safe, sin forma nueva en disco y sin
  migración.
- **Aviso blando.** Nada de esto bloquea una escritura (contrato BETA1-J02/J04);
  ni ``create_hito_manual`` ni ``update_entity`` cambian de comportamiento.
- **Agrupado, no volcado.** Un panel con 19 tarjetas idénticas es el fracaso que
  BETA-AUDIT-14 quiso evitar, así que ``grouped()`` reparte los avisos en tres
  familias con títulos humanos y separa «tu historia se contradice» de «tu
  calendario no cubre estas fechas».

No importa ``wiki_lint_service``, ``diagnostic_service`` ni ``issue_service``:
siguen en cuarentena por decisión escrita de BETA-AUDIT-14 y la Continuidad es
otra cosa (temporal/causal, no lint de wiki).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.application import causal_links
from packages.application.temporal_coherence import (
    TemporalIssue,
    evaluate_bilocation,
    evaluate_dating_sync,
    evaluate_entity,
    evaluate_knowledge,
    evaluate_milestone,
    evaluate_milestone_participants,
    evaluate_relation,
)
from packages.domain.result import Error, Ok, Result

#: Marcador de descarte (custom_metadata/metadata). Mismo patrón que
#: ``_struct_dismissed``: lista de huellas, append-safe, cero esquema.
DISMISS_KEY = "_continuity_dismissed"

#: Familias de aviso. La separación es de PRODUCTO, no cosmética: «mi serie se
#: contradice» es a lo que el usuario viene; «mi calendario no cubre estas
#: fechas» es información de encuadre y no puede pesar lo mismo.
FAMILIA_HISTORIA = "historia"
FAMILIA_DATACION = "datacion"
FAMILIA_CALENDARIO = "calendario"

FAMILIA_TITULOS: dict[str, str] = {
    FAMILIA_HISTORIA: "Tu historia se contradice",
    FAMILIA_DATACION: "Las fechas no cuadran entre sí",
    FAMILIA_CALENDARIO: "Tu calendario no cubre estas fechas",
}

#: (familia, título humano del grupo). El código técnico se conserva como id
#: estable —lo usan la huella y los tests—, pero no es lo que se le enseña a
#: nadie.
_CATALOGO: dict[str, tuple[str, str]] = {
    "T10_BILOCATION": (FAMILIA_HISTORIA, "En dos sitios a la vez"),
    "T11_PARTICIPANT_OUTSIDE_LIFE": (FAMILIA_HISTORIA, "Participa fuera de su vida"),
    "T12_KNOWS_AND_IGNORES": (FAMILIA_HISTORIA, "Sabe e ignora lo mismo a la vez"),
    "T13_KNOWS_BEFORE_REVELATION": (FAMILIA_HISTORIA, "Lo sabe antes de que se revele"),
    "T07_MILESTONE_BEFORE_PARENT": (FAMILIA_HISTORIA, "La consecuencia va antes que su causa"),
    "T05_EVENT_OUTSIDE_PARTICIPANT_LIFE": (
        FAMILIA_HISTORIA,
        "Participa en un evento fuera de su vida",
    ),
    "T04_RELATION_BEFORE_ENDPOINT": (
        FAMILIA_HISTORIA,
        "La relación empieza antes que sus extremos",
    ),
    "T04_RELATION_AFTER_ENDPOINT": (FAMILIA_HISTORIA, "La relación empieza tras morir un extremo"),
    "T06_CHILD_BEFORE_PARENT": (FAMILIA_HISTORIA, "Lo contenido empieza antes que su contenedor"),
    "T01_END_BEFORE_START": (FAMILIA_DATACION, "El fin va antes que el principio"),
    "T08_IMMORTAL_WITH_DEATH": (FAMILIA_DATACION, "Un inmortal con año de muerte"),
    "T09_ETERNAL_WITH_FINITE_BIRTH": (FAMILIA_DATACION, "Un eterno con nacimiento concreto"),
    "T14_DATING_DESYNC": (FAMILIA_DATACION, "La ficha y el lapso guardado no coinciden"),
    "T02_OUTSIDE_ERAS": (FAMILIA_CALENDARIO, "Fechas fuera de las eras del calendario"),
    "T03_START_AFTER_PRESENT": (FAMILIA_CALENDARIO, "Empieza después del presente"),
}

_ORDEN_FAMILIAS = (FAMILIA_HISTORIA, FAMILIA_DATACION, FAMILIA_CALENDARIO)

#: Canon que ya no cuenta: no se juzga lo descartado ni los fantasmas (un
#: placeholder manual no es una contradicción; sería ruido).
_EXCLUDED_CANON = frozenset({"descartado", "archivado", "obsoleto", "fantasma"})
_EXCLUDED_MILESTONE_STATUS = frozenset({"rejected", "archived"})


@dataclass(frozen=True)
class ContinuityGroup:
    """Un grupo de avisos del mismo código, ya contado y titulado."""

    code: str
    title: str
    family: str
    issues: list[TemporalIssue]

    @property
    def count(self) -> int:
        return len(self.issues)


def _canon_value(obj: Any) -> str:
    estado = getattr(obj, "canon_state", None)
    return str(getattr(estado, "value", estado) or "").lower()


def _status_value(obj: Any) -> str:
    estado = getattr(obj, "status", None)
    return str(getattr(estado, "value", estado) or "").lower()


@dataclass
class ContinuityService:
    """Reglas deterministas de coherencia temporal sobre el canon completo."""

    project_service: Any
    _cache_key: tuple[Any, Any] | None = field(default=None, init=False, repr=False)
    _cache: list[TemporalIssue] = field(default_factory=list, init=False, repr=False)
    #: Cuántas veces se recalculó de verdad (lo miran los tests de caché).
    computes: int = field(default=0, init=False, repr=False)

    def _proj(self):
        return getattr(self.project_service, "active_project", None)

    # ── API pública ──────────────────────────────────────────────────────

    def analyze(self) -> Result[list[TemporalIssue], str]:
        """Todos los avisos vigentes del proyecto (cacheado por ``_index_revision``)."""
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        key = (getattr(proj, "id", ""), getattr(proj, "_index_revision", 0))
        if self._cache_key == key:
            return Ok(list(self._cache))
        issues = self._compute(proj)
        self._cache_key = key
        self._cache = issues
        self.computes += 1
        return Ok(list(issues))

    def count(self) -> int:
        """Cuenta EXACTAMENTE lo que lista el panel (lección de FIX-05, ronda 1:
        la píldora y las tarjetas se descuadraron por contar cosas distintas)."""
        res = self.analyze()
        return len(res.value) if isinstance(res, Ok) else 0

    def grouped(self) -> Result[list[ContinuityGroup], str]:
        """Los avisos agrupados por código, en orden de familia y recuento."""
        res = self.analyze()
        if isinstance(res, Error):
            return res
        por_codigo: dict[str, list[TemporalIssue]] = {}
        for issue in res.value:
            por_codigo.setdefault(issue.code, []).append(issue)
        grupos = [
            ContinuityGroup(
                code=code,
                title=_CATALOGO.get(code, (FAMILIA_DATACION, code))[1],
                family=_CATALOGO.get(code, (FAMILIA_DATACION, code))[0],
                issues=issues,
            )
            for code, issues in por_codigo.items()
        ]
        grupos.sort(
            key=lambda g: (
                _ORDEN_FAMILIAS.index(g.family) if g.family in _ORDEN_FAMILIAS else 99,
                -g.count,
                g.code,
            )
        )
        return Ok(grupos)

    def loose_threads(self) -> Result[list[Any], str]:
        """«Plantado sin recoger»: hitos que ningún hito posterior recoge.

        Consume la definición ÚNICA del repo (``causal_links.loose_threads``,
        BETA2-FIX-09). Aquí no se reimplementa la consulta: la vieja
        medía ``caused_relation_ids`` y devolvía 20 de 20.
        """
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        return Ok(causal_links.loose_threads(proj))

    # ── Descartes (decisión del usuario, no hallazgo) ─────────────────────

    @staticmethod
    def fingerprint(issue: TemporalIssue) -> str:
        """Huella estable de un aviso: mismo canon ⇒ misma huella."""
        relacionados = "-".join(sorted(str(rid)[:8] for rid in issue.related_ids))
        return f"cont:{issue.subject_kind}:{issue.subject_id}:{issue.code}:{relacionados}"

    def dismiss(self, fingerprint: str) -> Result[bool, str]:
        """«No es un problema»: el aviso desaparece hasta que su huella cambie.

        Se guarda en el elemento afectado (``custom_metadata`` de entidad y
        relación, ``metadata`` del hito), como ``_struct_dismissed``. La UI no
        escribe: pide esto.
        """
        proj = self._proj()
        if proj is None:
            return Error("No hay proyecto activo")
        holder = self._holder(proj, str(fingerprint or ""))
        if holder is None:
            return Error("Elemento del aviso no encontrado")
        meta = self._meta_of(holder)
        actuales = list(meta.get(DISMISS_KEY) or [])
        if fingerprint not in actuales:
            actuales.append(fingerprint)
        meta[DISMISS_KEY] = actuales
        if hasattr(holder, "touch"):
            holder.touch()
        if hasattr(proj, "touch"):
            proj.touch()
        self._cache_key = None  # invalida el derive-on-read
        return Ok(True)

    def dismissed_count(self) -> int:
        """Cuántos avisos tiene descartados el proyecto (para poder decirlo)."""
        proj = self._proj()
        if proj is None:
            return 0
        total = 0
        for holder in self._holders(proj):
            total += len(self._meta_of(holder, create=False).get(DISMISS_KEY) or [])
        return total

    # ── Cálculo ───────────────────────────────────────────────────────────

    def _compute(self, proj: Any) -> list[TemporalIssue]:
        chronology = getattr(proj, "project_chronology", None)
        entities = {
            e.id: e
            for e in getattr(proj, "entities", []) or []
            if _canon_value(e) not in _EXCLUDED_CANON
        }
        relations = [
            r
            for r in getattr(proj, "relations", []) or []
            if _canon_value(r) not in _EXCLUDED_CANON
        ]
        milestones = [
            h
            for h in getattr(proj, "causal_milestones", []) or []
            if _status_value(h) not in _EXCLUDED_MILESTONE_STATUS
        ]

        issues: list[TemporalIssue] = []
        for entity in entities.values():
            issues += evaluate_entity(entity, chronology=chronology)
            issues += evaluate_dating_sync(entity)
        for relation in relations:
            issues += evaluate_relation(
                relation,
                source=entities.get(relation.source_id),
                target=entities.get(relation.target_id),
                chronology=chronology,
            )
        issues += evaluate_knowledge(relations, entities=entities, milestones=milestones)

        por_id = {h.id: h for h in milestones}
        for milestone in milestones:
            padres = [por_id[pid] for pid in milestone.causal_parent_hito_ids if pid in por_id]
            issues += evaluate_milestone(
                milestone, parent_milestones=padres, chronology=chronology
            )
            participantes = [
                entities[eid] for eid in milestone.affected_entity_ids if eid in entities
            ]
            issues += evaluate_milestone_participants(milestone, participantes)
        issues += evaluate_bilocation(milestones, entities)

        descartados = self._dismissed_fingerprints(entities, relations, milestones)
        if not descartados:
            return issues
        return [i for i in issues if self.fingerprint(i) not in descartados]

    # ── Marcadores de descarte ────────────────────────────────────────────

    @staticmethod
    def _meta_of(holder: Any, *, create: bool = True) -> dict:
        atributo = "custom_metadata" if hasattr(holder, "custom_metadata") else "metadata"
        meta = getattr(holder, atributo, None)
        if not isinstance(meta, dict):
            meta = {}
            if create:
                setattr(holder, atributo, meta)
        return meta

    @staticmethod
    def _holders(proj: Any):
        yield from getattr(proj, "entities", []) or []
        yield from getattr(proj, "relations", []) or []
        yield from getattr(proj, "causal_milestones", []) or []

    def _dismissed_fingerprints(self, entities, relations, milestones) -> set[str]:
        huellas: set[str] = set()
        for holder in (*entities.values(), *relations, *milestones):
            huellas.update(self._meta_of(holder, create=False).get(DISMISS_KEY) or [])
        return huellas

    def _holder(self, proj: Any, fingerprint: str):
        partes = fingerprint.split(":")
        if len(partes) < 3:
            return None
        kind, subject_id = partes[1], partes[2]
        if kind == "entity":
            coleccion = getattr(proj, "entities", []) or []
        elif kind == "relation":
            coleccion = getattr(proj, "relations", []) or []
        elif kind == "milestone":
            coleccion = getattr(proj, "causal_milestones", []) or []
        else:
            return None
        return next((obj for obj in coleccion if getattr(obj, "id", None) == subject_id), None)


__all__ = [
    "DISMISS_KEY",
    "FAMILIA_CALENDARIO",
    "FAMILIA_DATACION",
    "FAMILIA_HISTORIA",
    "FAMILIA_TITULOS",
    "ContinuityGroup",
    "ContinuityService",
]
