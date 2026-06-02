from __future__ import annotations

from copy import deepcopy

from packages.application.entity_service import EntityService
from packages.application.graph_models import GraphFilters, GraphOverlay, GraphViewType
from packages.application.graph_service import GraphService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.domain.candidate_issue import Candidate, StructuredIssue
from packages.domain.entity import EntityType, NarrativeEntity, VisibilityState
from packages.domain.result import Ok
from packages.domain.secrets_models import DeliveryState, Pista, RevelationState, Secreto
from packages.persistence.store import ProjectStore


def _setup():
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="B28")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    hs = HistoryService(project_service=ps)
    ss = SourceService(project_service=ps, store=store)
    qs = QueryService(entity_service=es, relation_service=rs, source_service=ss, history_service=hs)
    gs = GraphService(query_service=qs, relation_service=rs, entity_service=es)
    return ps, es, rs, gs


def _entity(es, name: str, etype: str, **data):
    payload = {"name": name, "entity_type": etype}
    payload.update(data)
    result = es.create_entity(payload)
    assert isinstance(result, Ok)
    return result.value


def test_build_specialized_graph_maps_each_view_type_without_mutating_project() -> None:
    ps, es, rs, gs = _setup()
    _entity(es, "Hero", "personaje")
    _entity(es, "City", "localizacion")
    _entity(es, "Secret", "secreto")
    before = deepcopy(ps.active_project.to_dict())

    for view_type in GraphViewType:
        view = gs.build_specialized_graph(GraphFilters(view_type=view_type)).value
        assert view.view_type == view_type
        assert view.stats is not None

    assert ps.active_project.to_dict() == before


def test_overlays_include_pending_candidates_and_open_issues_without_state_changes() -> None:
    ps, es, _, gs = _setup()
    hero = _entity(es, "Hero", "personaje")
    issue = StructuredIssue(description="Needs review", affected_entity_ids=[hero.id])
    candidate = Candidate(title="Candidate", affected_entity_ids=[hero.id])
    ps.active_project.issues.append(issue)
    ps.active_project.candidates.append(candidate)

    view = gs.build_specialized_graph(
        GraphFilters(overlays=[GraphOverlay.ISSUES, GraphOverlay.CANDIDATES]),
    ).value

    assert view.overlays["issues"][0]["id"] == issue.id
    assert view.overlays["candidates"][0]["id"] == candidate.id
    assert ps.active_project.issues[0].state.value == "abierta"
    assert ps.active_project.candidates[0].state.value == "pendiente"


def test_secret_and_clue_overlays_respect_player_no_leak_rules() -> None:
    ps, es, _, gs = _setup()
    secret_entity = _entity(
        es,
        "Secret Entity",
        "secreto",
        visibility_state=VisibilityState.PRIVADO_AUTOR,
    )
    clue_entity = _entity(es, "Clue Entity", "pista")
    ps.active_project.secrets.append(
        Secreto(
            content="Hidden truth",
            entity_id=secret_entity.id,
            revelation_state=RevelationState.oculto,
        ),
    )
    ps.active_project.clues.append(
        Pista(content="Pending clue", entity_id=clue_entity.id, delivery_state=DeliveryState.pendiente),
    )

    view = gs.build_specialized_graph(
        GraphFilters(
            view_type=GraphViewType.SECRETOS,
            overlays=[GraphOverlay.SECRETS, GraphOverlay.CLUES],
            audience="player",
        ),
    ).value
    dumped = str(view.to_dict())

    assert "Hidden truth" not in dumped
    assert "Pending clue" not in dumped
    assert all(node.id != secret_entity.id for node in view.nodes)


def test_clusters_by_domain_layer_and_faction_metadata_are_derived() -> None:
    ps, es, _, gs = _setup()
    faction_entity = _entity(es, "Faction", "faccion", domain_ids=["mundo"], layer_ids=["politica"])
    ps.active_project.factions.append(__import__("packages.domain.faction_models", fromlist=["Faction"]).Faction(entity_id=faction_entity.id, name="Faction"))

    view = gs.build_specialized_graph(GraphFilters(view_type=GraphViewType.FACCION)).value

    assert faction_entity.id in view.clusters["domain:mundo"]
    assert faction_entity.id in view.clusters["layer:politica"]
    assert faction_entity.id in view.clusters[f"faction:{ps.active_project.factions[0].id}"]


def test_compare_graph_views_reports_added_removed_changed() -> None:
    gs = GraphService(query_service=None, relation_service=None, entity_service=None)
    old = gs.graph_view_from_dict(
        {
            "nodes": [{"id": "n1", "label": "Old", "entity_type": "personaje"}],
            "edges": [{"id": "e1", "source_id": "n1", "target_id": "n2", "relation_type": "causo"}],
        },
    )
    new = gs.graph_view_from_dict(
        {
            "nodes": [
                {"id": "n1", "label": "New", "entity_type": "personaje"},
                {"id": "n2", "label": "Added", "entity_type": "evento"},
            ],
            "edges": [],
        },
    )

    comparison = gs.compare_graph_views(old, new, view_a_id="old", view_b_id="new").value

    assert [c.id for c in comparison.added_nodes] == ["n2"]
    assert [c.id for c in comparison.removed_edges] == ["e1"]
    assert comparison.changed_nodes[0].changes["label"] == ["Old", "New"]
