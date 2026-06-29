"""I31a — Cableado end-to-end de la pipeline nueva en ImportService.

`extract_graph_for_basket` orquesta MAP→REDUCE→STRUCTURE→DATE y puebla
`basket.graph`; `commit_graph_to_canon` lo materializa. Verifica consolidación
entre ventanas, agrupación, datación/relevancia aplicadas y el fallo claro sin IA.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.application.import_service import ImportService
from packages.domain.import_models import DocumentSegment, ImportBasket
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


class FakeProjectService:
    def __init__(self, project=None):
        self.active_project = project
        self._current_path = Path("/tmp/i31.json")


class _PipelineProvider(AIProvider):
    """Responde por fase: menciones en MAP (Aelar reaparece en 2 ventanas),
    una rama en la agrupación."""

    provider_name = "i31_pipe"

    def chat(self, system_prompt, user_message, timeout=None):
        if "extract_mentions" in user_message:
            if "ALFA" in user_message:
                return json.dumps({"mentions": [
                    {"kind": "entity", "name": "Aelar", "entity_type": "personaje",
                     "body": "Capitán de la guardia.", "birth_year": 100,
                     "relevance": 0.9, "confidence": 0.9},
                    {"kind": "entity", "name": "Lyra", "entity_type": "personaje",
                     "body": "Reina.", "relevance": 0.3, "confidence": 0.8},
                    {"kind": "relation", "source_name": "Aelar", "target_name": "Lyra",
                     "relation_type": "protege", "relevance": 0.7},
                ]}), None
            # Segunda ventana: Aelar reaparece (debe consolidarse, no duplicarse).
            return json.dumps({"mentions": [
                {"kind": "entity", "name": "Aelar", "entity_type": "personaje",
                 "body": "Reaparece en otra escena.", "relevance": 0.6},
            ]}), None
        if "group_entities_into_branches" in user_message:
            return json.dumps({"branches": [
                {"name": "Guardia de Marfil", "branch_type": "institucion",
                 "members": ["Aelar"]},
            ]}), None
        return json.dumps({}), None


def _project_with_basket():
    project = Project(id="p1", name="P")
    # Dos ventanas: seg1 normal (ALFA) + seg2 encabezado (fuerza ventana nueva).
    segs = [
        DocumentSegment(id="s0", source_id="src", raw_text="ALFA: Aelar y Lyra."),
        DocumentSegment(id="s1", source_id="src", raw_text="BETA: más sobre Aelar.",
                        metadata={"block_type": "heading"}),
    ]
    basket = ImportBasket(id="bk1", source_id="src", segments=segs)
    project.import_baskets.append(basket)
    return project, basket


def _svc(project):
    return ImportService(project_service=FakeProjectService(project))


def test_extract_graph_consolidates_across_windows_and_groups():
    project, basket = _project_with_basket()
    svc = _svc(project)
    res = svc.extract_graph_for_basket("bk1", provider=_PipelineProvider())
    assert is_ok(res)
    graph = unwrap(res)
    # Aelar de las dos ventanas → UNA entidad; + Lyra; + rama Guardia.
    leaves = [e for e in graph.entities if not e.is_branch]
    branches = [e for e in graph.entities if e.is_branch]
    names = sorted(e.name for e in leaves)
    assert names == ["Aelar", "Lyra"]
    assert len(branches) == 1 and branches[0].name == "Guardia de Marfil"
    # La rama contiene a Aelar (por id provisional).
    aelar = next(e for e in leaves if e.name == "Aelar")
    assert aelar.provisional_id in branches[0].member_ids
    # basket.graph poblado y candidatos viejos vaciados.
    assert basket.graph is not None
    assert basket.import_candidates == []


def test_extract_graph_applies_dating_and_relevance():
    project, basket = _project_with_basket()
    # Datación: era cerrada [0..50] → Aelar (birth 100) queda fuera de rango.
    project.project_chronology = type("C", (), {})()  # placeholder no usado
    svc = _svc(project)
    ctx = {"chronology_applied": {"eras": [{"name": "E", "start_year": 0, "end_year": 50}]}}
    graph = unwrap(svc.extract_graph_for_basket("bk1", provider=_PipelineProvider(),
                                                project_context=ctx))
    aelar = next(e for e in graph.entities if e.name == "Aelar")
    lyra = next(e for e in graph.entities if e.name == "Lyra")
    from packages.domain.import_models import DatingStatus, RelevanceTier
    assert aelar.dating_status is DatingStatus.FUERA_DE_RANGO
    assert aelar.relevance_tier is RelevanceTier.FUERTE   # 0.9
    assert lyra.relevance_tier is RelevanceTier.MARGINAL  # 0.3


def test_extract_graph_then_commit_populates_canon():
    project, basket = _project_with_basket()
    svc = _svc(project)
    unwrap(svc.extract_graph_for_basket("bk1", provider=_PipelineProvider()))
    res = svc.commit_graph_to_canon(basket.graph, basket_id="bk1")
    assert is_ok(res)
    # Aelar, Lyra, Guardia en canon + relaciones (contiene + protege).
    assert len(project.entities) == 3
    rtypes = sorted(r.relation_type.value for r in project.relations)
    assert "contiene" in rtypes and "protege" in rtypes


def test_extract_graph_without_real_provider_fails_clearly():
    project, basket = _project_with_basket()
    svc = _svc(project)
    # Sin proveedor → resuelve simulado → rechazado (no éxito simulado).
    res = svc.extract_graph_for_basket("bk1", allow_simulated=False)
    assert is_error(res)
    assert "proveedor" in res.error.lower()


def test_extract_graph_unknown_basket():
    project, _ = _project_with_basket()
    res = _svc(project).extract_graph_for_basket("nope", provider=_PipelineProvider())
    assert is_error(res)
