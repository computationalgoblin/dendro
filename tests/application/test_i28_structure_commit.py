"""I28 — Fase STRUCTURE: agrupación en ramas (garantías) + commit atómico a canon.

propose_structure: sin huérfanas (las hojas no agrupadas permanecen), sin ramas
vacías (rama sin miembros resolubles se descarta), anidamiento por IDs.
commit_graph_to_canon: materializa el subgrafo aceptado a canon resolviendo IDs
provisionales→reales, crea relaciones 'contiene', y revierte TODO ante un fallo.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.application.entity_service import EntityService
from packages.application.import_reconciliation_service import propose_structure
from packages.application.import_service import ImportService
from packages.domain.import_models import (
    ConsolidatedEntity,
    ConsolidatedRelation,
    ImportGraph,
)
from packages.domain.project import Project
from packages.domain.result import Error, is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i28-project.json")


def _ent(pid, name, kind="entity", **kw):
    return ConsolidatedEntity(provisional_id=pid, kind=kind, name=name, body=f"{name}.", **kw)


# ─────────────────────────── propose_structure ───────────────────────────


class _GroupingProvider(AIProvider):
    provider_name = "i28_group"

    def __init__(self, branches):
        self._branches = branches

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({"branches": self._branches}), None


def _graph_neddarya():
    return ImportGraph(entities=[
        _ent("imp_e_0001", "Ned"),
        _ent("imp_e_0002", "Arya"),
        _ent("imp_e_0003", "Bran"),  # quedará huérfano
    ])


def test_grouping_creates_branch_and_keeps_orphans():
    g = _graph_neddarya()
    provider = _GroupingProvider([
        {"name": "Casa Stark", "branch_type": "faccion", "members": ["Ned", "Arya"]},
    ])
    propose_structure(g, provider=provider)
    branches = [e for e in g.entities if e.is_branch]
    assert len(branches) == 1
    branch = branches[0]
    member_names = {g.entity_by_provisional_id(m).name for m in branch.member_ids}
    assert member_names == {"Ned", "Arya"}
    # Bran sigue presente (sin huérfanas) y NO es miembro.
    assert g.entity_by_provisional_id("imp_e_0003") is not None
    assert "imp_e_0003" not in branch.member_ids
    assert g.metadata["structure_applied"] is True


def test_grouping_skips_empty_branch():
    g = _graph_neddarya()
    provider = _GroupingProvider([
        {"name": "Casa Fantasma", "members": ["NadieResoluble"]},
    ])
    propose_structure(g, provider=provider)
    assert [e for e in g.entities if e.is_branch] == []  # rama vacía descartada


def test_grouping_nests_child_branch_in_parent():
    g = _graph_neddarya()
    provider = _GroupingProvider([
        {"name": "Casa Stark", "members": ["Ned", "Arya"]},
        {"name": "Reino del Norte", "members": ["Bran"], "parent": "Casa Stark"},
    ])
    propose_structure(g, provider=provider)
    stark = next(e for e in g.entities if e.name == "Casa Stark")
    reino = next(e for e in g.entities if e.name == "Reino del Norte")
    assert reino.provisional_id in stark.member_ids  # hija anidada en la madre


def test_grouping_degrades_without_provider():
    g = _graph_neddarya()
    propose_structure(g, provider=None)
    assert [e for e in g.entities if e.is_branch] == []


# ─────────────────────────── commit_graph_to_canon ───────────────────────────


def _svc(project=None):
    project = project or Project(id="p1", name="P")
    ps = FakeProjectService(project)
    return ImportService(project_service=ps), project


def test_commit_creates_entities_relations_and_containment():
    svc, project = _svc()
    g = ImportGraph(
        entities=[
            _ent("imp_e_0001", "Ned"),
            _ent("imp_e_0002", "Arya"),
            _ent("imp_b_0001", "Casa Stark", kind="branch", branch_type="faccion",
                 member_ids=["imp_e_0001", "imp_e_0002"]),
        ],
        relations=[ConsolidatedRelation(
            provisional_id="imp_r_0001", source_provisional_id="imp_e_0001",
            target_provisional_id="imp_e_0002", relation_type="es_aliado_de")],
    )
    res = svc.commit_graph_to_canon(g)
    assert is_ok(res)
    summary = unwrap(res)
    assert summary["created_entities"] == 3
    # 2 'contiene' (Casa→Ned, Casa→Arya) + 1 es_aliado_de.
    assert summary["created_relations"] == 3
    assert len(project.entities) == 3
    assert len(project.relations) == 3
    rtypes = sorted(r.relation_type.value for r in project.relations)
    assert rtypes == ["contiene", "contiene", "es_aliado_de"]


def test_commit_orphan_leaf_is_created():
    svc, project = _svc()
    g = ImportGraph(entities=[_ent("imp_e_0001", "Solitario")])
    assert is_ok(svc.commit_graph_to_canon(g))
    assert [e.name for e in project.entities] == ["Solitario"]


def test_commit_skips_empty_branch():
    svc, project = _svc()
    g = ImportGraph(entities=[
        _ent("imp_e_0001", "Ned"),
        _ent("imp_b_0001", "Casa", kind="branch", member_ids=["imp_e_0001"]),
    ])
    # Solo se acepta la rama; su único miembro NO se acepta → rama vacía → se omite.
    res = svc.commit_graph_to_canon(g, accepted_ids={"imp_b_0001"})
    summary = unwrap(res)
    assert summary["created_entities"] == 0
    assert "imp_b_0001" in summary["skipped_branches"]
    assert project.entities == []


def test_commit_is_atomic_rollback_on_failure():
    project = Project(id="p1", name="P")
    ps = FakeProjectService(project)

    class _FailOnArya(EntityService):
        def create_entity(self, data, history_service=None, *, enforce_dating=False):
            if data.get("name") == "Arya":
                return Error("fallo simulado")
            return super().create_entity(data, history_service, enforce_dating=enforce_dating)

    svc = ImportService(project_service=ps, entity_service=_FailOnArya(ps))
    g = ImportGraph(entities=[_ent("imp_e_0001", "Ned"), _ent("imp_e_0002", "Arya")])
    res = svc.commit_graph_to_canon(g)
    assert is_error(res)
    # Rollback: el proyecto queda intacto (sin la entidad creada antes del fallo).
    assert project.entities == []


def test_commit_empty_graph_is_ok():
    svc, project = _svc()
    res = svc.commit_graph_to_canon(ImportGraph())
    assert is_ok(res)
    assert unwrap(res)["created_entities"] == 0
