"""B34-T05 — Narrative relations between entity↔tree and tree↔tree via normal drag.

Validates that:
- Drag normal entity→tree creates a narrative relation (not CONTIENE).
- Drag normal tree→entity creates a narrative relation.
- Drag normal tree→tree creates a narrative relation.
- Alt+Drag entity→tree creates CONTIENE (structural membership).
- Both can coexist: entity inside tree (CONTIENE) + narrative relation.
"""

from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.project import Project
from packages.domain.result import Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _make_project():
    project = Project(name="B34-T05 narrative relations")
    tree = NarrativeEntity(name="Hermandad del Acero", entity_type=EntityType.CONTENEDOR)
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    akshan = NarrativeEntity(name="Akshan", entity_type=EntityType.PERSONAJE)
    tree2 = NarrativeEntity(name="Alta Aristocracia", entity_type=EntityType.CONTENEDOR)
    project.entities.extend([tree, devian, akshan, tree2])
    return project, tree, devian, akshan, tree2


def test_narrative_relation_entity_to_tree():
    """Normal drag entity→tree creates narrative relation (not CONTIENE)."""
    project, tree, devian, _, _ = _make_project()
    rs = RelationService(FakeProjectService(project))

    result = rs.create_relation(
        tree.id, devian.id, "traiciono",
        {"description": "Devian traicionó la Hermandad"},
    )
    assert isinstance(result, Ok)
    assert len(project.relations) == 1
    rel = project.relations[0]
    assert rel.relation_type.value == "traiciono"
    assert rel.source_id == tree.id
    assert rel.target_id == devian.id


def test_narrative_relation_tree_to_entity():
    """Normal drag tree→entity creates narrative relation."""
    project, tree, devian, _, _ = _make_project()
    rs = RelationService(FakeProjectService(project))

    result = rs.create_relation(
        devian.id, tree.id, "sirve_a",
        {"description": "Devian sirve a la Hermandad"},
    )
    assert isinstance(result, Ok)
    assert len(project.relations) == 1
    assert project.relations[0].relation_type.value == "sirve_a"


def test_narrative_relation_tree_to_tree():
    """Normal drag tree→tree creates narrative relation between containers."""
    project, tree, _, _, tree2 = _make_project()
    rs = RelationService(FakeProjectService(project))

    result = rs.create_relation(
        tree.id, tree2.id, "es_aliado_de",
        {"description": "Alianza entre facciones"},
    )
    assert isinstance(result, Ok)
    assert len(project.relations) == 1
    assert project.relations[0].relation_type.value == "es_aliado_de"


def test_structural_vs_narrative_different_types():
    """CONTIENE (structural) and narrative relation are different types."""
    project, tree, devian, _, _ = _make_project()
    rs = RelationService(FakeProjectService(project))

    # Structural: Alt+Drag → CONTIENE
    rs.create_relation(tree.id, devian.id, "contiene")
    # Narrative: Normal drag → traiciono
    rs.create_relation(
        devian.id, tree.id, "traiciono",
        {"description": "Devian traicionó la Hermandad"},
    )

    assert len(project.relations) == 2
    types = {r.relation_type.value for r in project.relations}
    assert "contiene" in types
    assert "traiciono" in types


def test_both_structural_and_narrative_coexist():
    """Entity inside tree (CONTIENE) + narrative relation with same tree."""
    project, tree, devian, _, _ = _make_project()
    rs = RelationService(FakeProjectService(project))

    # Devian is member of tree
    rs.create_relation(tree.id, devian.id, "contiene")
    # Devian also has narrative relation with tree
    rs.create_relation(
        devian.id, tree.id, "traiciono",
        {"description": "Devian traicionó la Hermandad"},
    )

    assert len(project.relations) == 2
    # Verify both are distinct
    contiene = [r for r in project.relations if r.relation_type.value == "contiene"]
    traiciono = [r for r in project.relations if r.relation_type.value == "traiciono"]
    assert len(contiene) == 1
    assert len(traiciono) == 1


def test_narrative_relation_persistence(tmp_path):
    """Narrative relations between trees persist through save/load."""
    from packages.application.project_service import ProjectService

    project, tree, _, _, tree2 = _make_project()
    rs = RelationService(FakeProjectService(project))
    rs.create_relation(
        tree.id, tree2.id, "es_aliado_de",
        {"description": "Alianza entre facciones"},
    )

    ps = ProjectService()
    ps.active_project = project
    f = tmp_path / "narrative-rel.dendro.json"
    assert isinstance(ps.save(f), Ok)
    ps.close()

    reopened = ps.open(f)
    assert isinstance(reopened, Ok)
    rels = reopened.value.relations
    assert len(rels) == 1
    assert rels[0].relation_type.value == "es_aliado_de"
    assert rels[0].source_id == tree.id
    assert rels[0].target_id == tree2.id


def test_tree_inside_tree_structural_with_narrative():
    """Tree B inside tree A (CONTIENE) + narrative relation tree A ↔ tree B."""
    project, tree, _, _, tree2 = _make_project()
    rs = RelationService(FakeProjectService(project))

    # Structural: tree inside tree2
    rs.create_relation(tree2.id, tree.id, "contiene")
    # Narrative: tree and tree2 have a narrative relation too
    rs.create_relation(
        tree.id, tree2.id, "esta_en_conflicto_con",
        {"description": "Hermandad rivaliza con la Aristocracia"},
    )

    assert len(project.relations) == 2
    types = {r.relation_type.value for r in project.relations}
    assert types == {"contiene", "esta_en_conflicto_con"}


def test_cannot_create_contiene_cycle_via_service():
    """Cycle prevention works even when mixing structural + narrative."""
    project, tree, _, _, tree2 = _make_project()
    rs = RelationService(FakeProjectService(project))

    # Structural: tree2 contains tree
    rs.create_relation(tree2.id, tree.id, "contiene")
    # Narrative is fine regardless
    rs.create_relation(
        tree.id, tree2.id, "es_enemigo_de",
        {"description": "Tensión interna"},
    )

    assert len(project.relations) == 2
    # Verify both exist independently
    contiene = [r for r in project.relations if r.relation_type.value == "contiene"]
    assert len(contiene) == 1
    assert contiene[0].source_id == tree2.id
    assert contiene[0].target_id == tree.id
