"""BETA2-MEM-04: motor de impacto (marca Falta regar por propagacion, sin IA)."""

from dataclasses import dataclass

import pytest

from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryTargetKind,
)
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.structured_reference import ReferenceStatus, StructuredReference
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakeProjectService:
    active_project: Project | None = None


def _entity(p, eid, name, layer=None):
    e = NarrativeEntity(id=eid, name=name, entity_type=EntityType.PERSONAJE)
    if layer:
        e.layer_ids = [layer]
    p.entities.append(e)
    return e


def _svc(p: Project):
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    return NarrativeImpactService(ps, memory_service=mem), mem, ps


def _regada_memory(mem, kind, target_id, text="contenido"):
    block = mem.upsert_memory(kind, target_id, resumen_editorial=text).value
    assert block.freshness == MemoryFreshness.REGADA
    return block


# ── relacion directa ────────────────────────────────────────────────────────


@pytest.mark.application
def test_impact_by_direct_relation_marks_and_preserves_content():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    _entity(p, "e2", "Beto")
    p.relations.append(
        NarrativeRelation(
            id="r", source_id="e1", target_id="e2", relation_type=RelationType.ES_ALIADO_DE
        )
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "e2", "Beto vive en el sur")

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")

    assert isinstance(result, Ok)
    assert ("entity", "e2") in result.value.marked_ids()
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e2").value
    assert block.freshness == MemoryFreshness.FALTA_REGAR
    assert block.resumen_editorial == "Beto vive en el sur"  # no borra (criterio 4)


@pytest.mark.application
def test_impact_by_mention_backlink():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    _entity(p, "e3", "Cita")
    p.structured_references.append(
        StructuredReference(
            source_kind=MemoryTargetKind.ENTITY, source_id="e3",
            target_kind=MemoryTargetKind.ENTITY, target_id="e1",
            alias="Ana", status=ReferenceStatus.RESUELTA,
        )
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "e3")

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")
    assert ("entity", "e3") in result.value.marked_ids()


@pytest.mark.application
def test_impact_by_memory_citation():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    _entity(p, "e4", "Dorotea")
    p.touch()
    impact, mem, _ = _svc(p)
    # La Memoria de e4 cita a e1 en sus dependencias.
    mem.upsert_memory(
        MemoryTargetKind.ENTITY, "e4", resumen_editorial="depende de Ana",
        dependencias=[MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="e1")],
    )

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")
    assert ("entity", "e4") in result.value.marked_ids()


# ── direccionalidad por anillos ───────────────────────────────────────────────


def _ringed_project():
    p = Project(id="p", name="P")
    upper = WorldLayer(id="ring_up", name="Cosmico")
    lower = WorldLayer(id="ring_dn", name="Politico")
    set_causal_rank(upper, 1)  # menor rank = anillo superior
    set_causal_rank(lower, 3)
    p.world_layers.extend([upper, lower])
    _entity(p, "U", "Dios", layer="ring_up")
    _entity(p, "L", "Rey", layer="ring_dn")
    return p


@pytest.mark.application
def test_descending_propagation_upper_to_lower():
    p = _ringed_project()
    p.relations.append(
        NarrativeRelation(id="r", source_id="U", target_id="L", relation_type=RelationType.GOBIERNA)
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "L")

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "U")  # cambia el superior
    assert ("entity", "L") in result.value.marked_ids()  # el inferior se marca


@pytest.mark.application
def test_ascending_not_propagated_without_causal_relation():
    p = _ringed_project()
    p.relations.append(
        NarrativeRelation(id="r", source_id="L", target_id="U", relation_type=RelationType.SIRVE_A)
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "U")

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "L")  # cambia el inferior
    assert ("entity", "U") not in result.value.marked_ids()  # el superior NO se marca


@pytest.mark.application
def test_ascending_propagated_with_explicit_causal_relation():
    p = _ringed_project()
    p.relations.append(
        NarrativeRelation(id="r", source_id="L", target_id="U", relation_type=RelationType.CAUSO)
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "U")

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "L")
    assert ("entity", "U") in result.value.marked_ids()  # excepcion ascendente explicita


# ── solo lo que ya tiene Memoria / estados de frescura ────────────────────────


@pytest.mark.application
def test_only_marks_elements_with_existing_memory_no_bloat():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    _entity(p, "e5", "SinMemoria")
    p.relations.append(
        NarrativeRelation(
            id="r", source_id="e1", target_id="e5", relation_type=RelationType.ES_ALIADO_DE
        )
    )
    p.touch()
    impact, mem, _ = _svc(p)
    # e5 no tiene Memoria: no debe marcarse ni crearse bloque.
    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")
    assert ("entity", "e5") not in result.value.marked_ids()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e5").value is None  # no se creo bloque


@pytest.mark.application
def test_secada_memory_is_not_clobbered():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    _entity(p, "e2", "Beto")
    p.relations.append(
        NarrativeRelation(
            id="r", source_id="e1", target_id="e2", relation_type=RelationType.ES_ALIADO_DE
        )
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "e2")
    mem.set_freshness(MemoryTargetKind.ENTITY, "e2", freshness=MemoryFreshness.SECADA)

    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")
    assert ("entity", "e2") not in result.value.marked_ids()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e2").value.freshness == MemoryFreshness.SECADA


@pytest.mark.application
def test_self_memory_marked():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "e1")
    result = impact.propagate_change(MemoryTargetKind.ENTITY, "e1")
    assert ("entity", "e1") in result.value.marked_ids()


@pytest.mark.application
def test_milestone_change_marks_affected_entity():
    p = Project(id="p", name="P")
    _entity(p, "e1", "Ana")
    p.causal_milestones.append(
        CausalMilestone(id="h1", title="La Caida", year=1, affected_entity_ids=["e1"])
    )
    p.touch()
    impact, mem, _ = _svc(p)
    _regada_memory(mem, MemoryTargetKind.ENTITY, "e1")

    result = impact.propagate_change(MemoryTargetKind.MILESTONE, "h1")
    assert ("entity", "e1") in result.value.marked_ids()


@pytest.mark.application
def test_no_active_project_errors():
    impact = NarrativeImpactService(_FakeProjectService(active_project=None))
    assert isinstance(impact.propagate_change(MemoryTargetKind.ENTITY, "e1"), Error)
