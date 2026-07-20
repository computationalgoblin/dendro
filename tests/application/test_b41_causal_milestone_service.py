import pytest

from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.project_service import ProjectService
from packages.domain.candidate_issue import CandidateState, CandidateType
from packages.domain.causal_milestone import CausalMilestoneStatus, CausalMilestoneType
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="B41")
    cs = CandidateService(ps)
    return ps, CausalMilestoneService(ps, candidate_service=cs), cs


@pytest.mark.application
def test_create_manual_hito_mutates_project_as_canon():
    ps, service, _ = _setup()

    result = service.create_hito_manual({
        "title": "Fundación del Pacto de Peso",
        "description": "La cultura acepta el equilibrio gravitatorio.",
        "milestone_type": "fundacion",
        "affected_entity_ids": ["ent_cultura"],
        "layer_ids": ["layer_historia"],
    })

    assert isinstance(result, Ok)
    hito = result.value
    assert hito.status == CausalMilestoneStatus.CANON
    assert hito.milestone_type == CausalMilestoneType.FUNDACION
    assert ps.active_project.causal_milestones == [hito]


@pytest.mark.application
def test_create_hito_candidate_is_review_only_until_approved():
    ps, service, candidate_service = _setup()

    candidate_result = service.create_hito_candidate({
        "title": "Guerra de la Marea Negra",
        "description": "Un conflicto que explica la frontera actual.",
        "affected_entity_ids": ["ent_frontera"],
        "caused_relation_ids": ["rel_conflicto"],
    }, source="ia", confidence=0.7)

    assert isinstance(candidate_result, Ok)
    candidate = candidate_result.value
    assert candidate.candidate_type == CandidateType.SUGERENCIA_IA
    assert candidate.state == CandidateState.PENDIENTE
    assert len(ps.active_project.causal_milestones) == 0

    approved = service.approve_hito(candidate.id)

    assert isinstance(approved, Ok)
    hito = approved.value
    assert hito.status == CausalMilestoneStatus.CANON
    assert hito.candidate_id == candidate.id
    assert candidate.state == CandidateState.ACEPTADO
    assert ps.active_project.causal_milestones[0].title == "Guerra de la Marea Negra"


@pytest.mark.application
def test_update_reject_and_list_hitos_by_targets():
    ps, service, _ = _setup()
    hito = service.create_hito_manual({
        "title": "Reforma del Calendario Lunar",
        "affected_entity_ids": ["leaf_1"],
        "affected_branch_ids": ["branch_1"],
        "affected_layer_ids": ["ring_1"],
        "caused_relation_ids": ["rel_1"],
    }).value

    updated = service.update_hito(hito.id, {"description": "Actualizado", "tags": ["calendario"]})

    assert isinstance(updated, Ok)
    assert updated.value.description == "Actualizado"
    assert updated.value.tags == ["calendario"]
    assert service.list_hitos_for_leaf("leaf_1").value == [hito]
    assert service.list_hitos_for_branch("branch_1").value == [hito]
    assert service.list_hitos_for_ring("ring_1").value == [hito]
    assert service.list_hitos_for_relation("rel_1").value == [hito]

    rejected = service.reject_hito(hito.id)

    assert isinstance(rejected, Ok)
    assert hito.status == CausalMilestoneStatus.REJECTED


@pytest.mark.application
def test_causal_chain_and_gap_detection_helpers():
    ps, service, _ = _setup()
    parent = service.create_hito_manual({"id": "h_parent", "title": "Origen"}).value
    child = service.create_hito_manual({
        "id": "h_child",
        "title": "Consecuencia",
        "causal_parent_hito_ids": ["h_parent"],
        "caused_relation_ids": ["rel_explained"],
    }).value
    parent.causal_child_hito_ids.append(child.id)
    ps.active_project.relations.append(NarrativeRelation(
        id="rel_explained",
        source_id="a",
        target_id="b",
        relation_type=RelationType.DERIVA_DE,
    ))
    ps.active_project.relations.append(NarrativeRelation(
        id="rel_orphan",
        source_id="c",
        target_id="d",
        relation_type=RelationType.CONDICIONA,
    ))

    chain = service.list_causal_chain("h_parent")
    relations_without_hito = service.find_relations_without_hito()
    hitos_without_consequences = service.find_hitos_without_consequences()

    assert isinstance(chain, Ok)
    assert [h.id for h in chain.value] == ["h_parent", "h_child"]
    assert isinstance(relations_without_hito, Ok)
    assert [r.id for r in relations_without_hito.value] == ["rel_orphan"]
    assert isinstance(hitos_without_consequences, Ok)
    assert [h.id for h in hitos_without_consequences.value] == ["h_parent"]


# ── Subhitos: contención temporal de 1 nivel (BETA2-SUB-01) ──────────────────


@pytest.mark.application
def test_set_and_list_subhitos():
    ps, service, _ = _setup()
    guerra = service.create_hito_manual({"title": "La Gran Guerra", "year": 100}).value
    b1 = service.create_hito_manual({"title": "Batalla A", "year": 102}).value
    b2 = service.create_hito_manual({"title": "Batalla B", "year": 101}).value

    assert isinstance(service.set_milestone_parent(b1.id, guerra.id), Ok)
    assert isinstance(service.set_milestone_parent(b2.id, guerra.id), Ok)

    subhitos = service.list_subhitos(guerra.id)
    assert isinstance(subhitos, Ok)
    # ordenados por año
    assert [h.title for h in subhitos.value] == ["Batalla B", "Batalla A"]
    assert b1.parent_milestone_id == guerra.id


@pytest.mark.application
def test_set_parent_rejects_two_levels_and_self():
    ps, service, _ = _setup()
    guerra = service.create_hito_manual({"title": "Guerra", "year": 1}).value
    batalla = service.create_hito_manual({"title": "Batalla", "year": 2}).value
    escaramuza = service.create_hito_manual({"title": "Escaramuza", "year": 3}).value

    assert isinstance(service.set_milestone_parent(batalla.id, guerra.id), Ok)
    # el marco ya es subhito → 1 nivel
    assert isinstance(service.set_milestone_parent(escaramuza.id, batalla.id), Error)
    # auto-referencia
    assert isinstance(service.set_milestone_parent(guerra.id, guerra.id), Error)
    # un hito que ya contiene subhitos no puede volverse subhito
    assert isinstance(service.set_milestone_parent(guerra.id, escaramuza.id), Error)


@pytest.mark.application
def test_clear_parent_makes_first_level():
    ps, service, _ = _setup()
    guerra = service.create_hito_manual({"title": "Guerra", "year": 1}).value
    batalla = service.create_hito_manual({"title": "Batalla", "year": 2}).value
    service.set_milestone_parent(batalla.id, guerra.id)

    assert isinstance(service.clear_milestone_parent(batalla.id), Ok)
    assert batalla.parent_milestone_id is None
    assert service.list_subhitos(guerra.id).value == []


@pytest.mark.application
def test_create_subhito_convenience():
    ps, service, _ = _setup()
    guerra = service.create_hito_manual({"title": "Guerra", "year": 1}).value

    created = service.create_subhito(guerra.id, {"title": "Batalla del Vado", "year": 3})

    assert isinstance(created, Ok)
    assert created.value.parent_milestone_id == guerra.id
    assert [h.title for h in service.list_subhitos(guerra.id).value] == ["Batalla del Vado"]


@pytest.mark.application
def test_delete_marco_orphans_subhitos():
    ps, service, _ = _setup()
    guerra = service.create_hito_manual({"title": "Guerra", "year": 1}).value
    batalla = service.create_hito_manual({"title": "Batalla", "year": 2}).value
    service.set_milestone_parent(batalla.id, guerra.id)

    assert isinstance(service.delete_hito(guerra.id), Ok)

    # el subhito sigue existiendo pero ya sin marco
    assert any(h.id == batalla.id for h in ps.active_project.causal_milestones)
    assert batalla.parent_milestone_id is None
