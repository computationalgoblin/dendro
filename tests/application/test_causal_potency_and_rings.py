"""BETA2-MEM-08: potencia causal ligera, excepcion ascendente y propuesta ring_move."""

from dataclasses import dataclass

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.causal_potency import (
    build_ring_move_proposal,
    get_ascending_exception,
    get_basal_potency,
    is_ascending_exception,
    set_ascending_exception,
    set_basal_potency,
)
from packages.application.entity_service import EntityService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.relation_service import RelationService
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _ringed_project():
    p = Project(id="p", name="P")
    upper = WorldLayer(id="ring_up", name="Cosmico")
    lower = WorldLayer(id="ring_dn", name="Politico")
    set_causal_rank(upper, 1)
    set_causal_rank(lower, 3)
    p.world_layers.extend([upper, lower])
    u = NarrativeEntity(id="U", name="Dios", entity_type=EntityType.PERSONAJE)
    u.layer_ids = ["ring_up"]
    lo = NarrativeEntity(id="L", name="Rey", entity_type=EntityType.PERSONAJE)
    lo.layer_ids = ["ring_dn"]
    p.entities.extend([u, lo])
    return p


# ── potencia basal ligera ──────────────────────────────────────────────────────


@pytest.mark.application
def test_basal_potency_derives_from_ring_rank():
    p = _ringed_project()
    u = p.entity_by_id("U")
    lo = p.entity_by_id("L")
    assert get_basal_potency(p, u) == 100  # anillo superior (rank 1)
    assert get_basal_potency(p, lo) == 88  # anillo inferior (rank 3)


@pytest.mark.application
def test_basal_potency_annotation_overrides_derivation():
    p = _ringed_project()
    lo = p.entity_by_id("L")
    set_basal_potency(lo, 95)
    assert get_basal_potency(p, lo) == 95
    set_basal_potency(lo, None)
    assert get_basal_potency(p, lo) == 88  # vuelve a la derivada


@pytest.mark.application
def test_basal_potency_default_without_ring():
    p = Project(id="p", name="P")
    e = NarrativeEntity(id="e", name="Suelto")
    p.entities.append(e)
    assert get_basal_potency(p, e) == 50


# ── excepcion ascendente ────────────────────────────────────────────────────────


@pytest.mark.application
def test_ascending_exception_set_get():
    rel = NarrativeRelation(id="r", source_id="a", target_id="b")
    assert is_ascending_exception(rel) is False
    set_ascending_exception(rel, "apalancamiento")
    assert is_ascending_exception(rel) is True
    assert get_ascending_exception(rel) == "apalancamiento"
    set_ascending_exception(rel, "invalido")  # tipo no valido -> se limpia
    assert is_ascending_exception(rel) is False


@pytest.mark.application
def test_impact_ascending_only_with_exception_tag():
    p = _ringed_project()
    rel = NarrativeRelation(
        id="r", source_id="L", target_id="U", relation_type=RelationType.ES_ALIADO_DE
    )
    p.relations.append(rel)
    p.touch()
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.ENTITY, "U", resumen_editorial="dios")
    impact = NarrativeImpactService(ps, memory_service=mem)

    # Sin etiqueta: el cambio inferior NO escala al superior.
    res = impact.propagate_change(MemoryTargetKind.ENTITY, "L")
    assert ("entity", "U") not in res.value.marked_ids()

    # Con excepcion ascendente: SI escala.
    mem.set_freshness(MemoryTargetKind.ENTITY, "U", freshness=MemoryFreshness.REGADA)
    set_ascending_exception(rel, "catalizador")
    res2 = impact.propagate_change(MemoryTargetKind.ENTITY, "L")
    assert ("entity", "U") in res2.value.marked_ids()


# ── propuesta estructural ring_move ──────────────────────────────────────────────


@pytest.mark.application
def test_ring_move_candidate_moves_entity_and_propagates_impact():
    p = _ringed_project()
    # dependiente en el anillo inferior, relacionado con U, con Memoria vigente
    dep = NarrativeEntity(id="dep", name="Sacerdote", entity_type=EntityType.PERSONAJE)
    dep.layer_ids = ["ring_dn"]
    p.entities.append(dep)
    p.relations.append(
        NarrativeRelation(id="r", source_id="U", target_id="dep", relation_type=RelationType.GOBIERNA)
    )
    p.touch()
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.ENTITY, "dep", resumen_editorial="sirve a U")

    proposal = build_ring_move_proposal(
        "U", current_ring_id="ring_up", target_ring_id="ring_dn",
        reasons=["ha perdido influencia cosmica"],
    )
    cand = Candidate(candidate_type=CandidateType.ANILLO, title="Bajar a U", proposed_data=proposal)
    p.candidates.append(cand)

    cs = CandidateService(
        project_service=ps,
        entity_service=EntityService(ps),
        relation_service=RelationService(ps),
    )
    impact = NarrativeImpactService(ps, memory_service=mem)
    result = cs.accept_candidate(cand.id, impact_service=impact)

    from packages.domain.result import Ok

    assert isinstance(result, Ok)
    # la entidad se movio de anillo (swap de layer_ids)
    assert p.entity_by_id("U").layer_ids == ["ring_dn"]
    # aceptar disparo impacto: el dependiente quedo Falta regar
    assert mem.get_memory(MemoryTargetKind.ENTITY, "dep").value.freshness == MemoryFreshness.FALTA_REGAR
