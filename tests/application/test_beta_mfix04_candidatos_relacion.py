"""BETA-MULTIAGENT-FIX-04: candidatos de relación IA cableados y honestos (G-04).

- El tipo aprobado es el tipo persistido; un tipo fuera de dominio se rechaza con
  error claro (nada de aplanar en silencio a esta_relacionado_con).
- Typo del dominio corregido: "conoce" funciona y "cono..." legado carga sin pérdida.
- Relación con extremo HITO → error en español que lo explica; la semilla no se
  marca aceptada.
- Entidad IA sin anillo hereda el del context_scope del candidato.
- Hito candidato con tipo/padres causales propuestos → persistidos.
"""

from __future__ import annotations

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.candidate_issue import CandidateState
from packages.domain.causal_milestone import CausalMilestoneType
from packages.domain.relation import NarrativeRelation, RelationType, coerce_relation_type
from packages.domain.result import Error
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(store=ProjectStore())
    ps.create(name="FIX-04")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, CandidateService(ps, es, rs), es, rs


def _pair(es):
    e1 = es.create_entity({"name": "Otho", "entity_type": "personaje"}).value
    e2 = es.create_entity({"name": "Mara", "entity_type": "personaje"}).value
    return e1, e2


# ── Fidelidad y rechazo del tipo ────────────────────────────────────────────


def test_tipo_aprobado_es_el_persistido():
    ps, svc, es, _ = _setup()
    e1, e2 = _pair(es)
    c = svc.create_candidate({
        "title": "Sirve a", "candidate_type": "relacion",
        "proposed_data": {"source_id": e1.id, "target_id": e2.id, "relation_type": "sirve_a"},
    }).value
    result = svc.accept_candidate(c.id)
    assert not isinstance(result, Error)
    assert ps.active_project.relations[0].relation_type is RelationType.SIRVE_A


def test_tipo_fuera_de_dominio_se_rechaza_con_error_claro():
    ps, svc, es, _ = _setup()
    e1, e2 = _pair(es)
    c = svc.create_candidate({
        "title": "Mentor", "candidate_type": "relacion",
        "proposed_data": {"source_id": e1.id, "target_id": e2.id, "relation_type": "mentor"},
    }).value
    result = svc.accept_candidate(c.id)
    assert isinstance(result, Error)
    assert "mentor" in result.error
    assert "esta_relacionado_con" in result.error  # sugiere tipos válidos
    assert ps.active_project.relations == []  # nada aplanado en silencio
    assert c.state == CandidateState.PENDIENTE


def test_tipo_vacio_cae_al_default_explicito():
    ps, svc, es, _ = _setup()
    e1, e2 = _pair(es)
    c = svc.create_candidate({
        "title": "Sin tipo", "candidate_type": "relacion",
        "proposed_data": {"source_id": e1.id, "target_id": e2.id},
    }).value
    result = svc.accept_candidate(c.id)
    assert not isinstance(result, Error)
    assert ps.active_project.relations[0].relation_type is RelationType.ESTA_RELACIONADO_CON


# ── Typo CONOCE + alias legado ──────────────────────────────────────────────


def test_conoce_funciona_y_legado_carga_sin_perdida():
    assert RelationType.CONOCE.value == "conoce"
    assert coerce_relation_type("conoce") is RelationType.CONOCE
    assert coerce_relation_type("cono...") is RelationType.CONOCE  # alias de carga
    legacy = NarrativeRelation.from_dict(
        {"source_id": "a", "target_id": "b", "relation_type": "cono..."}
    )
    assert legacy.relation_type is RelationType.CONOCE
    assert legacy.to_dict()["relation_type"] == "conoce"  # re-guarda el valor bueno


# ── Relación con extremo HITO ───────────────────────────────────────────────


def test_relacion_con_hito_da_error_en_espanol_y_no_acepta():
    from packages.application.causal_milestone_service import CausalMilestoneService

    ps, svc, es, _ = _setup()
    e1, _ = _pair(es)
    hito = CausalMilestoneService(ps).create_hito_manual(
        {"title": "El incendio", "milestone_type": "ruptura", "year": 100}
    ).value
    c = svc.create_candidate({
        "title": "Rel a hito", "candidate_type": "relacion",
        "proposed_data": {"source_id": e1.id, "target_id": hito.id, "relation_type": "causo"},
    }).value
    result = svc.accept_candidate(c.id)
    assert isinstance(result, Error)
    assert "HITO" in result.error
    assert "entidades" in result.error
    assert c.state == CandidateState.PENDIENTE


# ── Herencia de anillo desde el scope ───────────────────────────────────────


def test_entidad_sin_anillo_hereda_el_del_scope():
    from packages.domain.world_layer import WorldLayer

    ps, svc, _, _ = _setup()
    ps.active_project.world_layers.append(WorldLayer(id="layer_corte", name="La Corte", order=1))
    c = svc.create_candidate({
        "title": "Nueva dama", "candidate_type": "entidad",
        "proposed_data": {"name": "Zoraida", "entity_type": "personaje"},
        "metadata": {"context_scope": {"active_ring_id": "layer_corte"}},
    }).value
    result = svc.accept_candidate(c.id)
    assert not isinstance(result, Error)
    created = ps.active_project.entities[0]
    assert created.layer_ids == ["layer_corte"]


# ── Hito candidato con tipo y padres causales ───────────────────────────────


def test_hito_candidato_persiste_tipo_y_padres():
    from packages.application.causal_milestone_service import CausalMilestoneService

    ps, svc, _, _ = _setup()
    padre = CausalMilestoneService(ps).create_hito_manual(
        {"title": "El pacto", "milestone_type": "pacto", "year": 90}
    ).value
    c = svc.create_candidate({
        "title": "Hito sugerido", "candidate_type": "sugerencia_ia",
        "proposed_data": {
            "kind": "causal_milestone",
            "milestone": {
                "title": "La revelación",
                "milestone_type": "revelacion",
                "year": 110,
                "causal_parent_hito_ids": [padre.id],
            },
        },
    }).value
    result = svc.accept_candidate(c.id)
    assert not isinstance(result, Error)
    nuevo = ps.active_project.causal_milestones[-1]
    assert nuevo.milestone_type is CausalMilestoneType.REVELACION
    assert nuevo.causal_parent_hito_ids == [padre.id]
