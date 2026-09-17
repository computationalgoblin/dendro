"""BETA-FIX-01: el riego no se auto-invalida (G-01, 4/4 testers).

Regar propaga «Falta regar» a las relacionadas, pero los miembros del MISMO lote
de riego quedan excluidos: sin esto, un lote de vecinas jamás acababa verde (solo
la última regada quedaba `regada`) y el badge 💧 invitaba a re-regar en bucle.
Para riegos separados en el tiempo la propagación se mantiene a conciencia
(contrato: docs/contracts/wiki_memoria.md §propagación, excepción del lote).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from packages.application.ai_jobs import AIJobService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.watering_service import WateringService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.infrastructure.ai_provider import AIProvider

_VALID_PAYLOAD = {
    "scores": {"arraigo": 50, "nutrida": 60, "iluminada": 40},
    "summary": "Diagnóstico de prueba.",
    "metric_explanations": {
        "arraigo": "ok",
        "nutrida": "ok",
        "iluminada": "ok",
    },
    "risks": [],
}


class _FakeWateringProvider(AIProvider):
    provider_name = "fake_watering"
    model = "fake-model-1"

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        return json.dumps(_VALID_PAYLOAD, ensure_ascii=False), None


@dataclass
class _PS:
    active_project: Project = None


class _StubMemoryAI:
    """update_memory que siempre escribe la página como regada (sin IA real)."""

    def __init__(self, memory_service):
        self._memories = memory_service

    def update_memory(self, kind, target_id, mode="regar", progress_callback=None):
        self._memories.upsert_memory(
            kind, target_id, resumen_editorial="regada", freshness=MemoryFreshness.REGADA
        )
        return Ok({"target_id": target_id})


@dataclass
class _RecordingImpact:
    calls: list = field(default_factory=list)

    def propagate_change(
        self,
        kind,
        changed_id,
        *,
        cause_hint="",
        include_self=True,
        exclude_ids=None,
        only_via=None,
    ):
        self.calls.append(
            {
                "changed_id": changed_id,
                "include_self": include_self,
                "exclude_ids": set(exclude_ids or ()),
                # BETA2-FIX-05: el camino de Regar restringe las vías.
                "only_via": None if only_via is None else set(only_via),
            }
        )
        return Ok(None)


def _project_abc() -> tuple[_PS, dict[str, str]]:
    proj = Project(name="Jardín FIX-01")
    ids = {}
    for name in ("A", "B", "C", "D"):
        e = NarrativeEntity(name=name, entity_type=EntityType.PERSONAJE)
        proj.entities.append(e)
        ids[name] = e.id
    for src, dst in (("A", "B"), ("B", "C"), ("B", "D")):
        proj.relations.append(
            NarrativeRelation(
                source_id=ids[src],
                target_id=ids[dst],
                relation_type=RelationType.ESTA_RELACIONADO_CON,
            )
        )
    return _PS(active_project=proj), ids


# ── Motor de impacto: exclusión del lote ────────────────────────────────────


def test_propagate_excluye_miembros_del_lote():
    ps, ids = _project_abc()
    memories = NarrativeMemoryService(ps)
    for name in ("A", "B", "C"):
        memories.upsert_memory(
            MemoryTargetKind.ENTITY,
            ids[name],
            resumen_editorial="p",
            freshness=MemoryFreshness.REGADA,
        )
    impact = NarrativeImpactService(ps, memories)
    res = impact.propagate_change(
        MemoryTargetKind.ENTITY,
        ids["B"],
        cause_hint="regar",
        include_self=False,
        exclude_ids=frozenset({ids["A"], ids["C"]}),
    )
    assert isinstance(res, Ok)
    marked = {m.target_id for m in res.value.marks}
    assert ids["A"] not in marked and ids["C"] not in marked  # compañeras de lote
    # La propia B tampoco (include_self=False intacto).
    assert ids["B"] not in marked
    fresh_a = memories.get_memory(MemoryTargetKind.ENTITY, ids["A"]).value.freshness
    assert fresh_a == MemoryFreshness.REGADA


def test_propagate_sin_exclusion_marca_relacionadas_regadas():
    """El MOTOR sigue marcando por `relacion` cuando no se restringen las vías.

    BETA2-FIX-05: esto es el comportamiento del motor para un cambio de
    CANON (update_entity/accept_candidate…), que es lo que no se puede romper. El
    camino de Regar ya NO llega aquí sin `only_via` — ver
    `test_water_entity_restringe_la_propagacion_a_dependencia_real`.
    """
    ps, ids = _project_abc()
    memories = NarrativeMemoryService(ps)
    memories.upsert_memory(
        MemoryTargetKind.ENTITY, ids["A"], resumen_editorial="p", freshness=MemoryFreshness.REGADA
    )
    impact = NarrativeImpactService(ps, memories)
    res = impact.propagate_change(
        MemoryTargetKind.ENTITY, ids["B"], cause_hint="regar", include_self=False
    )
    assert isinstance(res, Ok)
    assert ids["A"] in {m.target_id for m in res.value.marks}


def test_propagate_marca_dependiente_no_regado():
    """Las relacionadas NO regadas siguen marcándose aunque haya exclusión de lote."""
    ps, ids = _project_abc()
    memories = NarrativeMemoryService(ps)
    memories.upsert_memory(
        MemoryTargetKind.ENTITY, ids["D"], resumen_editorial="p", freshness=MemoryFreshness.REGADA
    )
    impact = NarrativeImpactService(ps, memories)
    res = impact.propagate_change(
        MemoryTargetKind.ENTITY,
        ids["B"],
        cause_hint="regar",
        include_self=False,
        exclude_ids=frozenset({ids["A"], ids["C"]}),  # D NO está en el lote
    )
    assert isinstance(res, Ok)
    assert ids["D"] in {m.target_id for m in res.value.marks}


# ── Cableado del riego: el lote viaja hasta el motor ────────────────────────


def _watering(ps) -> tuple[WateringService, _RecordingImpact]:
    memories = NarrativeMemoryService(ps)
    impact = _RecordingImpact()
    ai = AIJobService(
        provider=_FakeWateringProvider(), project_provider=lambda: ps.active_project
    )
    svc = WateringService(
        ps,
        ai_job_service=ai,
        memory_ai_service=_StubMemoryAI(memories),
        impact_service=impact,
        memory_service=memories,
    )
    return svc, impact


def test_water_batch_step_pasa_el_lote_como_exclusion():
    ps, ids = _project_abc()
    svc, impact = _watering(ps)
    lote = [ids["A"], ids["B"], ids["C"]]
    for entity_id in lote:
        result = svc.water_batch_step(entity_id, batch_ids=lote)
        assert isinstance(result, Ok), getattr(result, "error", "")
    assert len(impact.calls) == 3
    for call in impact.calls:
        assert call["include_self"] is False
        assert set(lote) <= call["exclude_ids"]


def test_water_entity_suelto_no_excluye_a_nadie():
    ps, ids = _project_abc()
    svc, impact = _watering(ps)
    result = svc.water_entity(ids["B"])
    assert isinstance(result, Ok), getattr(result, "error", "")
    assert impact.calls and impact.calls[-1]["exclude_ids"] == set()


def test_water_entity_restringe_la_propagacion_a_dependencia_real():
    """BETA2-FIX-05 (G2-05): Regar no propaga por la vía `relacion`.

    Regar reescribe una página de wiki; no cambia canon. La exclusión de lote de
    FIX-01 tapaba el síntoma solo dentro de una autorización; la restricción de vías
    lo cierra también entre riegos separados.
    """
    ps, ids = _project_abc()
    svc, impact = _watering(ps)
    assert isinstance(svc.water_entity(ids["B"]), Ok)
    assert impact.calls
    only_via = impact.calls[-1]["only_via"]
    assert only_via == {"mencion", "cita_memoria"}
    assert "relacion" not in only_via
