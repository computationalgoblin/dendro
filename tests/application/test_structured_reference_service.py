"""BETA2-MEM-03: StructuredReferenceService (resolución, ambigüedad, backlinks)."""

from dataclasses import dataclass

import pytest

from packages.application.structured_reference_service import (
    StructuredReferenceService,
    backlinks_for,
    build_known_targets,
    resolve_references,
)
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.domain.structured_reference import ReferenceStatus
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakeProjectService:
    active_project: Project | None = None


def _project() -> Project:
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Aria", entity_type=EntityType.PERSONAJE))
    p.entities.append(NarrativeEntity(id="e2", name="Aria", entity_type=EntityType.PERSONAJE))
    p.entities.append(NarrativeEntity(id="e3", name="Bob", entity_type=EntityType.PERSONAJE))
    p.entities.append(NarrativeEntity(id="b1", name="Casa Stark", entity_type=EntityType.FACCION))
    p.causal_milestones.append(CausalMilestone(id="h1", title="La Gran Guerra", year=1))
    p.world_layers.append(WorldLayer(id="r1", name="Politica"))
    return p


def _svc(project: Project | None = None):
    ps = _FakeProjectService(active_project=project if project is not None else _project())
    return StructuredReferenceService(ps), ps


# ── build_known_targets ─────────────────────────────────────────────────────


@pytest.mark.application
def test_build_known_targets_covers_kinds():
    known = build_known_targets(_project())
    by_id = {i: (n, k) for i, n, k in known}
    assert by_id["e3"] == ("Bob", "entity")
    assert by_id["b1"] == ("Casa Stark", "branch")  # rama = entidad contenedora
    assert by_id["h1"] == ("La Gran Guerra", "milestone")
    assert by_id["r1"] == ("Politica", "ring")


# ── resolución pura ─────────────────────────────────────────────────────────


@pytest.mark.application
def test_resolve_single_match_by_kind():
    p = _project()
    refs = resolve_references(
        p,
        MemoryTargetKind.ENTITY,
        "src",
        {"f": "Ver @Bob y @Casa Stark en @La Gran Guerra y @Politica"},
    )
    by_target = {(r.target_kind.value, r.target_id) for r in refs if r.is_resolved()}
    assert ("entity", "e3") in by_target
    assert ("branch", "b1") in by_target
    assert ("milestone", "h1") in by_target
    assert ("ring", "r1") in by_target


@pytest.mark.application
def test_resolve_duplicate_name_is_ambiguous_not_silent():
    p = _project()
    refs = resolve_references(p, MemoryTargetKind.ENTITY, "src", {"f": "Sobre @Aria"})
    assert len(refs) == 1
    ref = refs[0]
    assert ref.status == ReferenceStatus.AMBIGUA
    assert ref.target_id == ""  # no se elige uno en silencio (criterio 3)
    assert set(ref.candidate_target_ids) == {"e1", "e2"}


@pytest.mark.application
def test_resolve_unknown_is_unresolved_with_clean_alias():
    p = _project()
    refs = resolve_references(
        p, MemoryTargetKind.ENTITY, "src", {"f": "Habló con @Zephyr sobre todo"}
    )
    assert len(refs) == 1
    assert refs[0].status == ReferenceStatus.NO_RESUELTA
    assert refs[0].alias == "Zephyr"  # primera palabra, no la frase entera


@pytest.mark.application
def test_hint_binds_exact_id_over_ambiguity():
    p = _project()
    refs = resolve_references(
        p, MemoryTargetKind.ENTITY, "src", {"f": "Sobre @Aria"},
        hints={"aria": ("entity", "e2")},
    )
    assert refs[0].status == ReferenceStatus.RESUELTA
    assert refs[0].target_id == "e2"


# ── servicio: sync + backlinks + reparación ─────────────────────────────────


@pytest.mark.application
def test_no_active_project_errors():
    svc = StructuredReferenceService(_FakeProjectService(active_project=None))
    assert isinstance(svc.sync_element_references(MemoryTargetKind.ENTITY, "e1", {"f": "x"}), Error)


@pytest.mark.application
def test_sync_stores_and_backlinks_on_demand():
    svc, ps = _svc()
    result = svc.sync_element_references(
        MemoryTargetKind.ENTITY, "e3", {"brief_description": "Bob conoce a @Casa Stark"}
    )
    assert isinstance(result, Ok)
    back = svc.backlinks(MemoryTargetKind.BRANCH, "b1")
    assert isinstance(back, Ok)
    assert len(back.value) == 1
    assert back.value[0].source_id == "e3"


@pytest.mark.application
def test_backlinks_survive_rename():
    """La ref apunta a id: renombrar el target no rompe el backlink (criterio 2)."""
    p = _project()
    svc, ps = _svc(p)
    svc.sync_element_references(MemoryTargetKind.ENTITY, "e3", {"f": "con @Casa Stark"})
    # "renombrar" la rama (el nombre es un campo más; el id no cambia)
    next(e for e in p.entities if e.id == "b1").name = "Casa Lannister"
    back = svc.backlinks(MemoryTargetKind.BRANCH, "b1").value
    assert len(back) == 1  # sigue resolviendo por id


@pytest.mark.application
def test_sync_is_idempotent_and_partial_per_field():
    svc, ps = _svc()
    two_fields = {"brief_description": "@Bob", "extended_description": "@Politica"}
    svc.sync_element_references(MemoryTargetKind.ENTITY, "e1", two_fields)
    first = len(ps.active_project.structured_references)
    # re-sync mismo texto → mismo número (idempotente)
    svc.sync_element_references(MemoryTargetKind.ENTITY, "e1", two_fields)
    assert len(ps.active_project.structured_references) == first
    # actualizar solo un campo NO borra las refs del otro campo
    svc.sync_element_references(
        MemoryTargetKind.ENTITY, "e1", {"brief_description": "sin menciones"}
    )
    fields = {r.source_field for r in svc.references_of(MemoryTargetKind.ENTITY, "e1").value}
    assert "extended_description" in fields  # preservado
    assert "brief_description" not in fields  # recomputado a vacío


@pytest.mark.application
def test_unresolved_and_repair():
    svc, ps = _svc()
    svc.sync_element_references(MemoryTargetKind.ENTITY, "e3", {"f": "Sobre @Aria"})
    pending = svc.unresolved().value
    assert len(pending) == 1 and pending[0].status == ReferenceStatus.AMBIGUA
    fixed = svc.resolve_reference(pending[0].id, MemoryTargetKind.ENTITY, "e1")
    assert isinstance(fixed, Ok)
    assert fixed.value.status == ReferenceStatus.RESUELTA
    assert fixed.value.target_id == "e1"
    assert svc.unresolved().value == []


@pytest.mark.application
def test_backlinks_for_pure_helper():
    p = _project()
    svc, _ = _svc(p)
    svc.sync_element_references(MemoryTargetKind.ENTITY, "e3", {"f": "@Bob"})  # se auto-menciona
    hits = backlinks_for(p, MemoryTargetKind.ENTITY, "e3")
    assert len(hits) == 1
