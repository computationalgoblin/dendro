"""BETA2-STRUCT-09: detector estructural sobre la potencia causal ATRIBUIDA.

El anillo clasifica la potencialidad de propagación causal, pero esa potencia la atribuye la IA
de forma semántica (al Regar) en `custom_metadata["_causal_potency_basal"]`. El detector solo LEE
esa métrica y compara con el anillo — determinista. Sin métrica atribuida → no se juzga (silencio
honesto). Ya NO se usa la topología (conectividad) como potencial: confundía "muy conectado" con
"causa fundamental".
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.causal_potency import (
    get_ascending_exception,
    set_ascending_exception,
    set_basal_potency,
)
from packages.application.entity_service import EntityService
from packages.application.foco_rings import contained_descendant_ids
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.relation_service import RelationService
from packages.application.structural_analysis_service import StructuralAnalysisService
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.candidate_issue import CandidateType
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _FakeAI:
    """Doble del AIJobService para probar enrich_justification (borde IA)."""

    text: str | None = None
    err: str | None = None
    unconfigured: bool = False
    raise_it: bool = False

    def provider_unconfigured(self) -> bool:
        return self.unconfigured

    def raw_json_completion(self, system: str, user: str) -> tuple[str | None, str | None]:
        if self.raise_it:
            raise RuntimeError("boom")
        return (self.text, self.err)


def _project(ranks: tuple[int, ...] = (1, 2, 3)) -> tuple[Project, list[str]]:
    """Proyecto con N anillos rankeados (posiciones 1..N por causal_rank)."""
    p = Project(id="p", name="P")
    rings: list[str] = []
    for i, rank in enumerate(ranks, start=1):
        layer = WorldLayer(id=f"r{i}", name=f"Anillo{i}")
        set_causal_rank(layer, rank)
        p.world_layers.append(layer)
        rings.append(layer.id)
    return p, rings


def _add(p: Project, eid: str, ring_id: str, potency: int | None = None) -> NarrativeEntity:
    e = NarrativeEntity(id=eid, name=eid)
    if ring_id:
        e.layer_ids = [ring_id]
    if potency is not None:
        set_basal_potency(e, potency)
    p.entities.append(e)
    p.touch()
    return e


def _svc(p: Project) -> StructuralAnalysisService:
    return StructuralAnalysisService(_FakeProjectService(active_project=p))


# ── detección sobre la potencia atribuida ─────────────────────────────────


@pytest.mark.application
def test_high_potency_in_outer_ring_moves_upstream():
    p, rings = _project()
    _add(p, "guerra", rings[2], potency=95)  # potencia alta pero en el anillo exterior
    findings = _svc(p).analyze().value
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "ring_move"
    assert f.target_id == "guerra"
    assert f.proposed_data["target_ring_id"] == rings[0]  # aguas-arriba
    assert f.proposed_data["current_ring_id"] == rings[2]
    assert f.confidence >= 0.6


@pytest.mark.application
def test_low_potency_in_inner_ring_moves_outward():
    p, rings = _project()
    _add(p, "campesino", rings[0], potency=5)  # potencia baja pero en el anillo superior
    findings = _svc(p).analyze().value
    assert len(findings) == 1
    assert findings[0].proposed_data["target_ring_id"] == rings[2]  # exterior


@pytest.mark.application
def test_single_band_mismatch_now_fires():
    # Con potencia semántica, un desajuste de 1 banda ya dispara (umbral gap>=1).
    p, rings = _project((1, 5))  # 2 anillos: posiciones 1 y 2
    _add(p, "corte", rings[1], potency=90)  # potencia alta pero en el anillo exterior (pos2)
    findings = _svc(p).analyze().value
    assert len(findings) == 1
    assert findings[0].proposed_data["target_ring_id"] == rings[0]  # sube una banda
    assert findings[0].confidence >= 0.6


@pytest.mark.application
def test_unannotated_entity_is_ignored():
    p, rings = _project()
    _add(p, "sin_metrica", rings[2], potency=None)
    # Silencio honesto: sin potencia atribuida por la IA, no se juzga.
    assert _svc(p).analyze().value == []


@pytest.mark.application
def test_matched_potency_no_finding():
    p, rings = _project()
    _add(p, "dios", rings[0], potency=95)  # potencia alta y ya en el anillo superior
    assert _svc(p).analyze().value == []


@pytest.mark.application
def test_expected_position_is_absolute_mapping_of_potency():
    # Mapeo absoluto: 100 → posición 1 (arriba), 0 → posición N (exterior), 50 → centro.
    assert StructuralAnalysisService._expected_position(100, 3) == 1
    assert StructuralAnalysisService._expected_position(0, 3) == 3
    assert StructuralAnalysisService._expected_position(50, 3) == 2
    # No depende del anillo actual de la entidad → no circular por construcción.


# ── supresión de decisiones ───────────────────────────────────────────────


@pytest.mark.application
def test_dismiss_filters_finding():
    p, rings = _project()
    _add(p, "guerra", rings[2], potency=95)
    svc = _svc(p)
    f = svc.analyze().value[0]
    assert isinstance(svc.dismiss(f.fingerprint), Ok)
    assert svc.analyze().value == []


@pytest.mark.application
def test_postpone_filters_until_next_change():
    p, rings = _project()
    _add(p, "guerra", rings[2], potency=95)
    svc = _svc(p)
    f = svc.analyze().value[0]
    assert isinstance(svc.postpone(f.fingerprint), Ok)
    assert svc.analyze().value == []  # aplazado al rev actual
    p.touch()  # un cambio de canon posterior
    assert len(svc.analyze().value) == 1  # reaparece


# ── caché derive-on-read ──────────────────────────────────────────────────


@pytest.mark.application
def test_analyze_caches_by_index_revision():
    p, rings = _project()
    _add(p, "guerra", rings[2], potency=95)
    svc = _svc(p)
    first = svc.analyze()
    assert svc._cache_key is not None
    assert svc.analyze().value[0].fingerprint == first.value[0].fingerprint


# ── preview_entity_dependents (dry-run sin escribir Memoria) ───────────────


@pytest.mark.application
def test_preview_entity_dependents_does_not_write_memory():
    p, rings = _project()
    _add(p, "U", rings[0])
    _add(p, "dep", rings[2])
    p.relations.append(
        NarrativeRelation(
            id="r", source_id="U", target_id="dep", relation_type=RelationType.GOBIERNA
        )
    )
    p.touch()
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.ENTITY, "dep", resumen_editorial="sirve a U")
    mem.set_freshness(MemoryTargetKind.ENTITY, "dep", freshness=MemoryFreshness.REGADA)
    impact = NarrativeImpactService(ps, memory_service=mem)

    deps = impact.preview_entity_dependents("U")
    assert any(d[1] == "dep" for d in deps)  # descendente → dependiente
    assert (
        mem.get_memory(MemoryTargetKind.ENTITY, "dep").value.freshness == MemoryFreshness.REGADA
    )


# ── integración: hallazgo → candidato → aceptar mueve la entidad ───────────


@pytest.mark.application
def test_as_candidate_and_accept_moves_entity():
    p, rings = _project()
    _add(p, "guerra", rings[2], potency=95)
    ps = _FakeProjectService(active_project=p)
    svc = StructuralAnalysisService(ps)
    f = svc.analyze().value[0]
    cand = svc.as_candidate(f)
    assert cand.candidate_type == CandidateType.ANILLO
    assert cand.proposed_data["kind"] == "ring_move"
    assert cand.affected_entity_ids == ["guerra"]
    p.candidates.append(cand)

    cs = CandidateService(
        project_service=ps,
        entity_service=EntityService(ps),
        relation_service=RelationService(ps),
    )
    res = cs.accept_candidate(cand.id)
    assert isinstance(res, Ok)
    assert p.entity_by_id("guerra").layer_ids == [rings[0]]  # movido aguas-arriba


# ── excepciones ascendentes (STRUCT-05) ────────────────────────────────────


def _relate(p: Project, rid: str, sid: str, tid: str, rtype: RelationType) -> NarrativeRelation:
    rel = NarrativeRelation(id=rid, source_id=sid, target_id=tid, relation_type=rtype)
    p.relations.append(rel)
    p.touch()
    return rel


def _ascending(findings) -> list:
    return [f for f in findings if f.kind == "ascending_exception"]


@pytest.mark.application
def test_ascending_exception_detected_for_noncausal_low_to_high():
    p, rings = _project()
    # extremo inferior con potencia alta PERO en su banda (para no disparar ring_move):
    # 2 anillos bastan — potencia 75 → banda 1 de 2... mejor aislar filtrando por kind.
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    rel = _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)  # no causal
    findings = _ascending(_svc(p).analyze().value)
    assert len(findings) == 1
    f = findings[0]
    assert f.target_id == "sierva"
    assert f.proposed_data["relation_id"] == rel.id
    assert f.proposed_data["exception_kind"] == "apalancamiento"
    assert f.fingerprint == f"ascending_exception:sierva:{rel.id}"
    assert f.confidence >= 0.6


@pytest.mark.application
def test_no_ascending_for_causal_relation():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    _relate(p, "rel1", "sierva", "reina", RelationType.CAUSO)  # ya escala por sí misma
    assert _ascending(_svc(p).analyze().value) == []


@pytest.mark.application
def test_no_ascending_below_threshold_or_unannotated():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=50)  # bajo umbral
    _add(p, "reina", rings[0])
    _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    assert _ascending(_svc(p).analyze().value) == []
    p2, rings2 = _project()
    _add(p2, "sierva", rings2[2])  # sin potencia atribuida: silencio honesto
    _add(p2, "reina", rings2[0])
    _relate(p2, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    assert _ascending(_svc(p2).analyze().value) == []


@pytest.mark.application
def test_no_ascending_when_already_marked_or_wrong_direction():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    rel = _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    set_ascending_exception(rel, "catalizador")  # ya marcada
    assert _ascending(_svc(p).analyze().value) == []
    p2, rings2 = _project()
    _add(p2, "reina", rings2[0], potency=90)
    _add(p2, "sierva", rings2[2])
    _relate(p2, "rel1", "reina", "sierva", RelationType.GOBIERNA)  # alto→bajo: no aplica
    assert _ascending(_svc(p2).analyze().value) == []


@pytest.mark.application
def test_ascending_dismiss_suppresses():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    svc = _svc(p)
    f = _ascending(svc.analyze().value)[0]
    assert isinstance(svc.dismiss(f.fingerprint), Ok)
    assert _ascending(svc.analyze().value) == []


@pytest.mark.application
def test_ascending_as_candidate_and_accept_marks_relation():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    rel = _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    ps = _FakeProjectService(active_project=p)
    svc = StructuralAnalysisService(ps)
    f = _ascending(svc.analyze().value)[0]
    cand = svc.as_candidate(f)
    assert cand.candidate_type == CandidateType.RELACION
    assert cand.proposed_data["kind"] == "ascending_exception"
    assert set(cand.affected_entity_ids) == {"sierva", "reina"}
    p.candidates.append(cand)

    cs = CandidateService(
        project_service=ps,
        entity_service=EntityService(ps),
        relation_service=RelationService(ps),
    )
    res = cs.accept_candidate(cand.id)
    assert isinstance(res, Ok)
    assert get_ascending_exception(rel) == "apalancamiento"
    # la marca queda registrada como relación editada → propaga impacto a ambos extremos
    assert res.value.metadata.get("edited_relation_id") == rel.id


@pytest.mark.application
def test_ascending_accept_propagates_impact_to_both_ends():
    p, rings = _project()
    _add(p, "sierva", rings[2], potency=90)
    _add(p, "reina", rings[0])
    _relate(p, "rel1", "sierva", "reina", RelationType.GOBIERNA)
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    for eid in ("sierva", "reina"):
        mem.upsert_memory(MemoryTargetKind.ENTITY, eid, resumen_editorial="x")
        mem.set_freshness(MemoryTargetKind.ENTITY, eid, freshness=MemoryFreshness.REGADA)
    impact = NarrativeImpactService(ps, memory_service=mem)
    svc = StructuralAnalysisService(ps)
    cand = svc.as_candidate(_ascending(svc.analyze().value)[0])
    p.candidates.append(cand)
    cs = CandidateService(
        project_service=ps,
        entity_service=EntityService(ps),
        relation_service=RelationService(ps),
    )
    res = cs.accept_candidate(cand.id, impact_service=impact)
    assert isinstance(res, Ok)
    for eid in ("sierva", "reina"):
        freshness = mem.get_memory(MemoryTargetKind.ENTITY, eid).value.freshness
        assert freshness == MemoryFreshness.FALTA_REGAR


# ── branch_move (STRUCT-06): mover ramas con su contenido ──────────────────


def _add_branch(p: Project, eid: str, ring_id: str, potency: int | None = None):
    e = _add(p, eid, ring_id, potency)
    e.entity_type = EntityType.CONTENEDOR
    return e


def _contain(p: Project, rid: str, container: str, member: str) -> None:
    _relate(p, rid, container, member, RelationType.CONTIENE)


@pytest.mark.application
def test_contained_descendant_ids_transitive_with_cycle_guard():
    p, rings = _project()
    _add_branch(p, "rama", rings[2])
    _add(p, "hijo", rings[2])
    _add(p, "nieto", rings[2])
    _contain(p, "c1", "rama", "hijo")
    _contain(p, "c2", "hijo", "nieto")
    _contain(p, "c3", "nieto", "rama")  # ciclo mal formado: no debe colgar
    assert contained_descendant_ids(p, "rama") == ["hijo", "nieto"]


@pytest.mark.application
def test_branch_with_content_yields_branch_move_not_ring_move():
    p, rings = _project()
    _add_branch(p, "guerra", rings[2], potency=95)  # rama potente en el anillo exterior
    _add(p, "batalla", rings[2], potency=85)
    _contain(p, "c1", "guerra", "batalla")
    findings = _svc(p).analyze().value
    branch = [f for f in findings if f.kind == "branch_move"]
    assert len(branch) == 1
    f = branch[0]
    assert f.target_id == "guerra"
    assert f.proposed_data["member_ids"] == ["batalla"]
    assert f.proposed_data["target_ring_id"] == rings[0]  # agregada 90 → aguas-arriba
    # la rama NO aparece además como ring_move suelto (rompería la contención)
    assert all(x.target_id != "guerra" for x in findings if x.kind == "ring_move")


@pytest.mark.application
def test_branch_without_any_annotated_potency_is_silent():
    p, rings = _project()
    _add_branch(p, "rama", rings[2])
    _add(p, "hijo", rings[2])
    _contain(p, "c1", "rama", "hijo")
    assert [f for f in _svc(p).analyze().value if f.kind == "branch_move"] == []


@pytest.mark.application
def test_branch_aggregate_uses_member_potencies_when_container_unannotated():
    p, rings = _project()
    _add_branch(p, "rama", rings[2])  # sin potencia propia
    _add(p, "evento", rings[2], potency=90)
    _contain(p, "c1", "rama", "evento")
    branch = [f for f in _svc(p).analyze().value if f.kind == "branch_move"]
    assert len(branch) == 1
    assert branch[0].proposed_data["target_ring_id"] == rings[0]


@pytest.mark.application
def test_branch_move_accept_moves_container_and_subtree():
    p, rings = _project()
    _add_branch(p, "guerra", rings[2], potency=95)
    _add(p, "batalla", rings[2], potency=85)
    _add(p, "escaramuza", rings[2])
    _contain(p, "c1", "guerra", "batalla")
    _contain(p, "c2", "batalla", "escaramuza")
    ps = _FakeProjectService(active_project=p)
    svc = StructuralAnalysisService(ps)
    f = [x for x in svc.analyze().value if x.kind == "branch_move"][0]
    cand = svc.as_candidate(f)
    assert cand.candidate_type == CandidateType.ANILLO
    p.candidates.append(cand)
    cs = CandidateService(
        project_service=ps,
        entity_service=EntityService(ps),
        relation_service=RelationService(ps),
    )
    res = cs.accept_candidate(cand.id)
    assert isinstance(res, Ok)
    for eid in ("guerra", "batalla", "escaramuza"):
        assert p.entity_by_id(eid).layer_ids == [rings[0]]  # todo el subárbol movido


# ── enriquecimiento IA al abrir (provider-optional) ────────────────────────


def _finding(p: Project):
    _add(p, "guerra", p.world_layers[2].id, potency=95)
    return _svc(p).analyze().value[0]


@pytest.mark.application
def test_enrich_without_provider_returns_deterministic_baseline():
    p, _ = _project()
    f = _finding(p)
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p))  # sin ai_job_service
    res = svc.enrich_justification(f)
    assert isinstance(res, Ok)
    assert "potencialidad de propagación causal" in res.value  # razón determinista


@pytest.mark.application
def test_enrich_uses_provider_narrative_when_valid():
    p, _ = _project()
    f = _finding(p)
    ai = _FakeAI(text='{"justificacion": "Prosa narrativa coherente."}')
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p), ai_job_service=ai)
    before = dict(f.proposed_data)
    res = svc.enrich_justification(f)
    assert res.value == "Prosa narrativa coherente."
    assert f.proposed_data == before  # nunca muta proposed_data


@pytest.mark.application
def test_enrich_falls_back_on_bad_json_or_error_or_raise():
    p, _ = _project()
    f = _finding(p)
    ps = _FakeProjectService(active_project=p)
    for ai in (
        _FakeAI(text="no es json"),
        _FakeAI(text=None, err="límite"),
        _FakeAI(raise_it=True),
        _FakeAI(unconfigured=True),
    ):
        res = StructuralAnalysisService(ps, ai_job_service=ai).enrich_justification(f)
        assert isinstance(res, Ok)
        assert "potencialidad de propagación causal" in res.value  # cae a la base determinista
