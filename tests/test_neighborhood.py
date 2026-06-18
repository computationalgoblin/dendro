"""Tests para packages.application.neighborhood y build_neighborhood_pack.

CONO de autoridad: vecindario por saltos con decaimiento por distancia.
"""

from packages.application.neighborhood import decay_weight
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.domain.entity import CanonState, EntityType, NarrativeEntity, VisibilityState
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _builder(project):
    return NarrativeContextBuilder(FakeProjectService(project))


# --- decay_weight -----------------------------------------------------------

def test_decay_weight_contract():
    assert decay_weight(0) == 1.0
    assert decay_weight(1) == 1.0
    assert decay_weight(2) == 0.4
    assert decay_weight(3) == 0.1
    assert decay_weight(4) == 0.0
    assert decay_weight(99) == 0.0


# --- BFS pack ---------------------------------------------------------------

def _line_project():
    """A-B-C-D en línea (A busca B, B busca C, C busca D)."""
    project = Project(name="Line", description="A-B-C-D")
    nodes = {}
    for nid, name in (("A", "Alfa"), ("B", "Beta"), ("C", "Gamma"), ("D", "Delta")):
        nodes[nid] = NarrativeEntity(
            id=nid,
            name=name,
            entity_type=EntityType.PERSONAJE,
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_JUGADORES,
        )
    project.entities.extend(nodes.values())
    for i, (s, t) in enumerate((("A", "B"), ("B", "C"), ("C", "D"))):
        project.relations.append(NarrativeRelation(
            id=f"rel_{i}",
            source_id=s,
            target_id=t,
            relation_type=RelationType.BUSCA,
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_JUGADORES,
        ))
    return project


def test_build_pack_max_hops_2():
    pack = _builder(_line_project()).build_neighborhood_pack(["A"], max_hops=2)
    by_id = {it["entity_id"]: it for it in pack["items"]}
    # B en hop 1 (w 1.0), C en hop 2 (w 0.4); D fuera con max_hops=2.
    assert "A" not in by_id  # la semilla nunca entra en items
    assert by_id["B"]["hop"] == 1 and by_id["B"]["weight"] == 1.0
    assert by_id["C"]["hop"] == 2 and by_id["C"]["weight"] == 0.4
    assert "D" not in by_id


def test_build_pack_max_hops_3_includes_d():
    pack = _builder(_line_project()).build_neighborhood_pack(["A"], max_hops=3)
    by_id = {it["entity_id"]: it for it in pack["items"]}
    assert by_id["D"]["hop"] == 3 and by_id["D"]["weight"] == 0.1


def test_build_pack_no_selection_warns():
    pack = _builder(_line_project()).build_neighborhood_pack([], max_hops=2)
    assert pack["items"] == []
    assert "no_selection" in pack["warnings"]


def test_secret_neighbor_excluded_for_players():
    project = _line_project()
    # Hacer B secreto del mundo: no debe entrar para audiencia jugadores.
    for e in project.entities:
        if e.id == "B":
            e.visibility_state = VisibilityState.SECRETO_MUNDO
    pack = _builder(project).build_neighborhood_pack(["A"], audience="player", max_hops=2)
    ids = {it["entity_id"] for it in pack["items"]}
    assert "B" not in ids
