from types import SimpleNamespace

from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.domain.candidate_issue import Candidate, CandidateState, CandidateType
from packages.domain.entity import CanonState, EntityType, NarrativeEntity, VisibilityState
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.secrets_models import DeliveryState, Pista, RevelationState, Secreto


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _builder(project):
    return NarrativeContextBuilder(FakeProjectService(project))


def _sample_project():
    project = Project(name="Context Test", description="Proyecto de prueba")
    hero = NarrativeEntity(
        id="ent_hero",
        name="Ariadna",
        entity_type=EntityType.PERSONAJE,
        brief_description="Exploradora",
        extended_description="Busca una ciudad perdida.",
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
        private_notes="Sabe más de lo que dice",
        exportable_notes="Conocida por el grupo",
    )
    city = NarrativeEntity(
        id="ent_city",
        name="Namar",
        entity_type=EntityType.LOCALIZACION,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
    )
    hidden = NarrativeEntity(
        id="ent_hidden",
        name="Traidor oculto",
        entity_type=EntityType.PERSONAJE,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.SECRETO_MUNDO,
    )
    relation = NarrativeRelation(
        id="rel_1",
        source_id="ent_hero",
        target_id="ent_city",
        relation_type=RelationType.BUSCA,
        description="Ariadna busca Namar.",
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
    )
    project.entities.extend([hero, city, hidden])
    project.relations.append(relation)
    project.secrets.extend([
        Secreto(id="sec_hidden", content="El traidor es el mentor.", affected_entity_ids=["ent_hero"], revelation_state=RevelationState.oculto),
        Secreto(id="sec_revealed", content="Namar existe.", affected_entity_ids=["ent_hero"], revelation_state=RevelationState.revelado),
    ])
    project.clues.extend([
        Pista(id="clue_pending", content="Mapa no entregado", associated_secret_id="sec_hidden", entity_id="ent_hero", delivery_state=DeliveryState.pendiente),
        Pista(id="clue_delivered", content="Inscripción vista", associated_secret_id="sec_revealed", entity_id="ent_hero", delivery_state=DeliveryState.entregada),
    ])
    project.candidates.append(Candidate(
        id="cand_1",
        candidate_type=CandidateType.ENTIDAD,
        state=CandidateState.PENDIENTE,
        title="Hermano perdido",
        proposed_data={"name": "Ilan"},
        affected_entity_ids=["ent_hero"],
        confidence=0.7,
        justification="Puede enriquecer el arco.",
    ))
    return project


def test_builder_returns_minimal_context_without_project():
    ctx = NarrativeContextBuilder(SimpleNamespace(active_project=None)).build_for_entity("missing")
    assert ctx["schema"] == "narrative_context/v1"
    assert ctx["project"] is None
    assert ctx["constraints"]["ai_may_mutate_canon"] is False


def test_gm_context_includes_hidden_secret_and_private_notes():
    ctx = _builder(_sample_project()).build_for_entity("ent_hero", audience="gm")
    secret_contents = [secret["content"] for secret in ctx["knowledge"]["secrets"]]
    clue_contents = [clue["content"] for clue in ctx["knowledge"]["clues"]]
    assert "El traidor es el mentor." in secret_contents
    assert "Mapa no entregado" in clue_contents
    assert ctx["target"]["private_notes"] == "Sabe más de lo que dice"


def test_player_context_hides_unrevealed_secret_and_undelivered_clue():
    ctx = _builder(_sample_project()).build_for_entity("ent_hero", audience="player")
    secret_contents = [secret["content"] for secret in ctx["knowledge"]["secrets"]]
    clue_contents = [clue["content"] for clue in ctx["knowledge"]["clues"]]
    assert secret_contents == ["Namar existe."]
    assert clue_contents == ["Inscripción vista"]
    assert ctx["target"]["private_notes"] == ""


def test_player_context_redacts_private_entity_target():
    ctx = _builder(_sample_project()).build_for_entity("ent_hidden", audience="player")
    assert ctx["target"] == {"redacted": True, "reason": "not_visible_for_audience"}


def test_neighborhood_and_candidate_are_marked_non_canon():
    ctx = _builder(_sample_project()).build_for_entity("ent_hero", audience="gm")
    assert ctx["neighborhood"]["relations"][0]["relation_type"] == "busca"
    assert ctx["candidates"][0]["canonical_status"] == "candidate_non_canon"
    assert ctx["candidates"][0]["facts_status"] == "proposal_only_not_confirmed"
