"""BETA2-STRUCT-07: propuesta IA de ESTRUCTURA de anillos (crear/fusionar) + aceptación.

La IA propone bajo demanda crear anillos que faltan o fusionar redundantes (tarea holística,
abstracta para el usuario). Aceptar reutiliza `ring_template` (crear) o la rama nueva
`ring_merge` (reasigna miembros + borra el origen). Provider-optional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.application.structural_analysis_service import StructuralAnalysisService
from packages.application.world_layer_causal import set_causal_rank
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.domain.world_layer import WorldLayer


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _FakeAI:
    text: str | None = None
    err: str | None = None
    unconfigured: bool = False

    def provider_unconfigured(self) -> bool:
        return self.unconfigured

    def raw_json_completion(self, system: str, user: str) -> tuple[str | None, str | None]:
        return (self.text, self.err)


def _ringed_project() -> tuple[Project, list[str]]:
    p = Project(id="p", name="P")
    ids = []
    for i, rank in enumerate((1, 5), start=1):
        layer = WorldLayer(id=f"ring_{i}", name=f"Anillo{i}")
        set_causal_rank(layer, rank)
        p.world_layers.append(layer)
        ids.append(layer.id)
    return p, ids


# ── aceptación ring_merge ──────────────────────────────────────────────────


@pytest.mark.application
def test_ring_merge_reassigns_members_and_removes_source():
    p, ids = _ringed_project()
    src, dst = ids[0], ids[1]
    p.entities.append(NarrativeEntity(id="e1", name="E1", layer_ids=[src]))
    p.entities.append(NarrativeEntity(id="e2", name="E2", layer_ids=[src, "otra"]))
    p.entities.append(NarrativeEntity(id="e3", name="E3", layer_ids=[dst]))
    ps = _FakeProjectService(active_project=p)
    cand = Candidate(
        candidate_type=CandidateType.ANILLO,
        title="Fusionar",
        proposed_data={"kind": "ring_merge", "source_ring_id": src, "target_ring_id": dst},
    )
    p.candidates.append(cand)
    cs = CandidateService(
        project_service=ps, entity_service=EntityService(ps), relation_service=RelationService(ps)
    )
    res = cs.accept_candidate(cand.id)
    assert isinstance(res, Ok)
    assert src not in [wl.id for wl in p.world_layers]  # anillo origen eliminado
    assert p.entity_by_id("e1").layer_ids == [dst]  # reasignada al destino
    assert set(p.entity_by_id("e2").layer_ids) == {"otra", dst}  # dedup, conserva no-anillo
    assert p.entity_by_id("e3").layer_ids == [dst]  # ya estaba, intacta


@pytest.mark.application
def test_ring_merge_rejects_invalid_source_or_target():
    p, ids = _ringed_project()
    ps = _FakeProjectService(active_project=p)
    cand = Candidate(
        candidate_type=CandidateType.ANILLO,
        proposed_data={
            "kind": "ring_merge",
            "source_ring_id": "no_existe",
            "target_ring_id": ids[0],
        },
    )
    p.candidates.append(cand)
    cs = CandidateService(
        project_service=ps, entity_service=EntityService(ps), relation_service=RelationService(ps)
    )
    assert not isinstance(cs.accept_candidate(cand.id), Ok)  # Error, no rompe


# ── propuesta IA de estructura ──────────────────────────────────────────────


@pytest.mark.application
def test_propose_ring_structure_parses_create_and_merge():
    p, ids = _ringed_project()
    payload = {
        "crear": [{"nombre": "Economía y comercio", "descripcion": "banda que falta", "rank": 6}],
        "fusionar": [{"origen_id": ids[0], "destino_id": ids[1], "motivo": "casi vacío"}],
    }
    ai = _FakeAI(text=json.dumps(payload))
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p), ai_job_service=ai)
    res = svc.propose_ring_structure()
    assert isinstance(res, Ok)
    kinds = sorted(f.proposed_data["kind"] for f in res.value)
    assert kinds == ["ring_merge", "ring_template"]
    assert len(svc.structure_proposals()) == 2  # guardadas en sesión
    # descartar quita de la sesión
    svc.discard_structure_proposal(res.value[0].fingerprint)
    assert len(svc.structure_proposals()) == 1


@pytest.mark.application
def test_propose_ring_structure_without_provider_returns_error():
    p, _ = _ringed_project()
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p))  # sin ai_job_service
    assert not isinstance(svc.propose_ring_structure(), Ok)
    svc2 = StructuralAnalysisService(
        _FakeProjectService(active_project=p), ai_job_service=_FakeAI(unconfigured=True)
    )
    assert not isinstance(svc2.propose_ring_structure(), Ok)


@pytest.mark.application
def test_propose_ring_structure_bad_json_returns_error():
    p, _ = _ringed_project()
    svc = StructuralAnalysisService(
        _FakeProjectService(active_project=p), ai_job_service=_FakeAI(text="no es json")
    )
    assert not isinstance(svc.propose_ring_structure(), Ok)


# ── fix smoke: orden visual (causal_rank) + identidad narrativa en el prompt ─────


@pytest.mark.application
def test_parse_structure_create_carries_causal_rank():
    """La propuesta de CREAR anillo lleva causal_rank (fija el orden visual)."""
    p, _ = _ringed_project()
    payload = {"crear": [{"nombre": "El Concilio de las Sombras", "descripcion": "x", "rank": 2}]}
    ai = _FakeAI(text=json.dumps(payload))
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p), ai_job_service=ai)
    res = svc.propose_ring_structure()
    assert isinstance(res, Ok)
    create = next(f for f in res.value if f.proposed_data["kind"] == "ring_template")
    assert create.proposed_data["causal_rank"] == 2


@pytest.mark.application
def test_ring_template_accept_sets_causal_rank_so_ring_orders_by_band():
    """Aceptar un ring_template con causal_rank ordena el anillo nuevo por su banda,
    no al final. Antes solo se escribía ``order`` (mero desempate) → quedaba último."""
    from packages.application.foco_rings import effective_rank_map
    from packages.application.world_layer_causal import get_causal_rank

    p = Project(id="p", name="P")
    # Anillo existente SIN causal_rank (proyecto sin ranking manual), order alto.
    existing = WorldLayer(id="ring_old", name="Reino", order=1)
    p.world_layers.append(existing)
    ps = _FakeProjectService(active_project=p)
    cand = Candidate(
        candidate_type=CandidateType.ANILLO,
        title="Crear anillo",
        proposed_data={
            "kind": "ring_template",
            "ring_name": "Los Hilos del Destino",
            "description": "banda de máximo impacto",
            "order": 2,
            "causal_rank": 1,  # alto impacto → aguas-arriba → primero
        },
    )
    p.candidates.append(cand)
    cs = CandidateService(
        project_service=ps, entity_service=EntityService(ps), relation_service=RelationService(ps)
    )
    assert isinstance(cs.accept_candidate(cand.id), Ok)
    new_layer = next(wl for wl in p.world_layers if wl.name == "Los Hilos del Destino")
    assert get_causal_rank(new_layer) == 1  # causal_rank escrito
    rank_map = effective_rank_map(list(p.world_layers))
    # el anillo con causal_rank (bucket rankeado) va ANTES del que no lo tiene
    assert rank_map[new_layer.id] < rank_map[existing.id]


@pytest.mark.application
def test_ring_structure_context_feeds_narrative_identity_and_positions():
    """El contexto del prompt incluye identidad narrativa (para nombres diegéticos)
    y la POSICIÓN efectiva de cada anillo (ancla real, no causal_rank crudo=None)."""
    p, ids = _ringed_project()
    p.creative_config.identidad.premisa = "Un reino de almendros que sueña"
    p.creative_config.identidad.genero_principal = "fantasía"
    p.entities.append(NarrativeEntity(id="e1", name="La Guerra", layer_ids=[ids[0]]))
    p.entities[-1].custom_metadata["_causal_potency_basal"] = 90
    svc = StructuralAnalysisService(_FakeProjectService(active_project=p))
    ctx = json.loads(svc._ring_structure_context(p))
    assert ctx["proyecto"]["premisa"] == "Un reino de almendros que sueña"
    assert ctx["proyecto"]["genero"] == "fantasía"
    assert all("posicion" in r for r in ctx["anillos"])
    assert ctx["anillos"][0]["posicion"] == 1  # ordenados por posición efectiva
