"""BETA2-SHIP-07: integridad de canon al aceptar candidatos (auditoría de datos).

Tres bugs confirmados con sonda:
- #0 resolución de relación por nombre: una subcadena de una entidad anterior tapaba
  la coincidencia EXACTA posterior → relación enlazada a la entidad equivocada.
- #5 accept_candidate no idempotente: una 2ª aceptación duplicaba canon.
- #4 ring_merge dejaba referencias colgantes (relaciones/hitos/capas) al anillo borrado.
"""

from __future__ import annotations

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.result import Error, Ok
from packages.domain.world_layer import WorldLayer
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="Test")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, CandidateService(ps, es, rs), es, rs


# ── #0: resolución por nombre, exacta gana sobre subcadena ───────────────────


def test_relation_by_name_exact_wins_over_substring():
    ps, svc, es, _ = _setup()
    # Orden de inserción con la subcadena ANTES de la exacta: 'ana' ⊂ 'Susana'.
    es.create_entity({"name": "Susana", "entity_type": "personaje"})
    ana = es.create_entity({"name": "Ana", "entity_type": "personaje"}).value
    reino = es.create_entity({"name": "Reino", "entity_type": "lugar"}).value
    c = svc.create_candidate({
        "title": "Ana → Reino", "candidate_type": "relacion",
        "proposed_data": {
            "source_name": "Ana", "target_name": "Reino", "relation_type": "pertenece_a",
        },
    }).value
    assert isinstance(svc.accept_candidate(c.id), Ok)
    rel = ps.active_project.relations[-1]
    assert rel.source_id == ana.id, "la exacta 'Ana' debe ganar, no 'Susana' por subcadena"
    assert rel.target_id == reino.id


# ── #5: idempotencia — no re-materializar canon ──────────────────────────────


def test_double_accept_entity_does_not_duplicate():
    ps, svc, _, _ = _setup()
    c = svc.create_candidate({
        "title": "Eldrin", "candidate_type": "entidad",
        "proposed_data": {"name": "Eldrin", "entity_type": "personaje"},
    }).value
    assert isinstance(svc.accept_candidate(c.id), Ok)
    second = svc.accept_candidate(c.id)
    assert isinstance(second, Error), "la 2ª aceptación debe rechazarse"
    assert len([e for e in ps.active_project.entities if e.name == "Eldrin"]) == 1


# ── #4: ring_merge reconcilia TODAS las referencias al anillo borrado ─────────


def test_ring_merge_reconciles_dangling_references():
    ps, svc, es, rs = _setup()
    proj = ps.active_project
    proj.world_layers = [
        WorldLayer(id="ring_a", name="A"),
        WorldLayer(id="ring_b", name="B", metadata={"causal_parent_layer_ids": "ring_a"}),
        WorldLayer(id="ring_c", name="C", metadata={"causal_parent_layer_ids": "ring_a"}),
    ]
    a = es.create_entity({"name": "Miembro", "entity_type": "personaje"}).value
    a.layer_ids = ["ring_a"]
    b = es.create_entity({"name": "Otro", "entity_type": "personaje"}).value
    rel = rs.create_relation(a.id, b.id, "es_aliado_de").value
    rel.layer_ids = ["ring_a"]

    c = svc.create_candidate({
        "title": "Fusionar A→B", "candidate_type": "anillo",
        "proposed_data": {
            "kind": "ring_merge", "source_ring_id": "ring_a", "target_ring_id": "ring_b",
        },
    }).value
    assert isinstance(svc.accept_candidate(c.id), Ok)

    ring_ids = {wl.id for wl in proj.world_layers}
    assert "ring_a" not in ring_ids  # el origen desaparece
    assert "ring_a" not in (a.layer_ids or [])  # entidad reasignada
    assert "ring_b" in (a.layer_ids or [])
    assert "ring_a" not in (rel.layer_ids or []), "la relación no puede quedar en anillo fantasma"
    assert "ring_b" in (rel.layer_ids or [])
    # causal_parent: ring_c pasa a apuntar a ring_b; ring_b no se auto-referencia.
    meta_c = {wl.id: wl.metadata for wl in proj.world_layers}["ring_c"]
    assert "ring_a" not in meta_c.get("causal_parent_layer_ids", "")
    assert "ring_b" in meta_c.get("causal_parent_layer_ids", "")
    meta_b = {wl.id: wl.metadata for wl in proj.world_layers}["ring_b"]
    assert "ring_b" not in meta_b.get("causal_parent_layer_ids", ""), "sin auto-referencia"


def test_ring_merge_survives_roundtrip():
    ps, svc, es, rs = _setup()
    proj = ps.active_project
    proj.world_layers = [WorldLayer(id="ring_a", name="A"), WorldLayer(id="ring_b", name="B")]
    a = es.create_entity({"name": "Miembro", "entity_type": "personaje"}).value
    a.layer_ids = ["ring_a"]
    c = svc.create_candidate({
        "title": "Fusionar", "candidate_type": "anillo",
        "proposed_data": {
            "kind": "ring_merge", "source_ring_id": "ring_a", "target_ring_id": "ring_b",
        },
    }).value
    assert isinstance(svc.accept_candidate(c.id), Ok)
    from packages.domain.project import Project

    reloaded = Project.from_dict(proj.to_dict())
    assert "ring_a" not in {wl.id for wl in reloaded.world_layers}
    member = reloaded.entity_by_id(a.id)
    assert "ring_a" not in (member.layer_ids or [])
