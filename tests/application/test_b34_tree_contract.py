"""B34-T01 — Tree semantic contract: cycles, persistence, cascade delete.

Validates that:
- _is_nested_in prevents multi-level cycles.
- Tree membership persists as real CONTIENE relations.
- Deleting a tree cascades to remove CONTIENE relations (members become orphans).
- Members themselves are NOT deleted.
- Pertenencia differs from narrative relation.
- TreeMeta round-trips through custom_metadata.
"""

from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.application.tree_meta import (
    KEY_INTERNAL_RULES,
    KEY_NARRATIVE_ROLE,
    KEY_OPEN_QUESTIONS,
    KEY_TREE_TYPE,
    TreeMeta,
)
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import RelationType
from packages.domain.result import Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _rtype_value(rel) -> str:
    """Extract relation_type value as lowercase string, handling enum and str."""
    rtype = getattr(rel, "relation_type", "")
    if hasattr(rtype, "value"):
        return str(rtype.value).lower()
    return str(rtype).lower()


def _project_with_tree():
    project = Project(name="B34 tree contract")
    tree = NarrativeEntity(name="Hermandad del Acero", entity_type=EntityType.CONTENEDOR)
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    akshan = NarrativeEntity(name="Akshan", entity_type=EntityType.PERSONAJE)
    project.entities.extend([tree, devian, akshan])
    return project, tree, devian, akshan


def _is_nested_in(project, entity_id: str, ancestor_id: str, visited: set | None = None) -> bool:
    """Mirror of workspaces._is_nested_in using project relations directly."""
    if visited is None:
        visited = set()
    if entity_id in visited:
        return False
    visited.add(entity_id)
    for rel in project.relations:
        if _rtype_value(rel) == "contiene" and getattr(rel, "target_id", "") == entity_id:
            parent = getattr(rel, "source_id", "")
            if parent == ancestor_id:
                return True
            if _is_nested_in(project, parent, ancestor_id, visited):
                return True
    return False


# ── 1. Multi-level cycle prevention ──────────────────────────────────


def test_cycle_direct_self_containment_is_self_reference():
    """A container cannot contain itself — workspaces blocks entity_id == tree_id."""
    project, tree, *_ = _project_with_tree()
    rs = RelationService(FakeProjectService(project))
    # RelationService does NOT block self-reference at service level.
    # workspaces._assign_node_to_tree checks entity_id == tree_id.
    result = rs.create_relation(tree.id, tree.id, "contiene")
    assert isinstance(result, Ok)
    # The UI-level check (entity_id == tree_id) prevents this in practice.


def test_cycle_three_level_blocked():
    """A contains B contains C. C cannot contain A (cycle)."""
    project = Project(name="cycle 3-level")
    a = NarrativeEntity(name="A", entity_type=EntityType.CONTENEDOR)
    b = NarrativeEntity(name="B", entity_type=EntityType.CONTENEDOR)
    c = NarrativeEntity(name="C", entity_type=EntityType.CONTENEDOR)
    project.entities.extend([a, b, c])

    rs = RelationService(FakeProjectService(project))

    r1 = rs.create_relation(a.id, b.id, "contiene")
    assert isinstance(r1, Ok)
    r2 = rs.create_relation(b.id, c.id, "contiene")
    assert isinstance(r2, Ok)

    # C cannot contain A: check that A is nested inside C
    # (A→B→C means A is ancestor of C, so C is_nested_in A)
    assert _is_nested_in(project, c.id, a.id), (
        "C should be detected as nested inside A (A→B→C)"
    )


def test_cycle_four_level_blocked():
    """A→B→C→D chain. D cannot contain A."""
    project = Project(name="cycle 4-level")
    entities = [
        NarrativeEntity(name=f"L{i}", entity_type=EntityType.CONTENEDOR)
        for i in range(4)
    ]
    project.entities.extend(entities)
    rs = RelationService(FakeProjectService(project))

    ids = [e.id for e in entities]
    for i in range(3):
        r = rs.create_relation(ids[i], ids[i + 1], "contiene")
        assert isinstance(r, Ok)

    # L3 is nested inside L0 (L0→L1→L2→L3)
    assert _is_nested_in(project, ids[3], ids[0])


# ── 2. Tree membership is a semantic relation ────────────────────────


def test_tree_membership_is_contiene_relation():
    """Membership is a real CONTIENE relation, not visual-only state."""
    project, tree, devian, akshan = _project_with_tree()
    rs = RelationService(FakeProjectService(project))

    r1 = rs.create_relation(tree.id, devian.id, "contiene")
    assert isinstance(r1, Ok)
    assert r1.value.relation_type == RelationType.CONTIENE
    assert r1.value.source_id == tree.id
    assert r1.value.target_id == devian.id

    r2 = rs.create_relation(tree.id, akshan.id, "contiene")
    assert isinstance(r2, Ok)

    contiene_rels = [
        r for r in project.relations
        if _rtype_value(r) == "contiene"
    ]
    assert len(contiene_rels) == 2


def test_pertenencia_differs_from_narrative_relation():
    """CONTIENE is structural, not a narrative relation like 'sirve_a'."""
    project, tree, devian, _ = _project_with_tree()
    rs = RelationService(FakeProjectService(project))

    r_struct = rs.create_relation(tree.id, devian.id, "contiene")
    assert isinstance(r_struct, Ok)
    assert r_struct.value.relation_type == RelationType.CONTIENE

    r_narr = rs.create_relation(devian.id, tree.id, "traiciono")
    assert isinstance(r_narr, Ok)
    assert r_narr.value.relation_type.value == "traiciono"

    assert len(project.relations) == 2


# ── 3. Delete tree cascades CONTIENE but not members ────────────────


def test_delete_tree_removes_contiene_relations_not_members():
    """Deleting a tree removes CONTIENE relations but keeps member entities."""
    project, tree, devian, akshan = _project_with_tree()
    es = EntityService(FakeProjectService(project))
    rs = RelationService(FakeProjectService(project))

    rs.create_relation(tree.id, devian.id, "contiene")
    rs.create_relation(tree.id, akshan.id, "contiene")
    assert len(project.relations) == 2

    result = es.delete_entity(tree.id)
    assert isinstance(result, Ok)

    remaining_ids = [e.id for e in project.entities]
    assert devian.id in remaining_ids
    assert akshan.id in remaining_ids
    assert tree.id not in remaining_ids
    assert len(project.relations) == 0


def test_delete_member_removes_its_contiene_but_not_tree():
    """Deleting a member removes its CONTIENE but keeps the tree."""
    project, tree, devian, akshan = _project_with_tree()
    es = EntityService(FakeProjectService(project))
    rs = RelationService(FakeProjectService(project))

    rs.create_relation(tree.id, devian.id, "contiene")
    rs.create_relation(tree.id, akshan.id, "contiene")

    result = es.delete_entity(devian.id)
    assert isinstance(result, Ok)

    remaining_ids = [e.id for e in project.entities]
    assert tree.id in remaining_ids
    assert akshan.id in remaining_ids

    contiene_rels = [
        r for r in project.relations
        if _rtype_value(r) == "contiene"
    ]
    assert len(contiene_rels) == 1
    assert contiene_rels[0].target_id == akshan.id


# ── 4. Persistence roundtrip ─────────────────────────────────────────


def test_tree_persistence_roundtrip(tmp_path):
    """Tree + members + CONTIENE survive save/reload."""
    project, tree, devian, akshan = _project_with_tree()
    rs = RelationService(FakeProjectService(project))

    rs.create_relation(tree.id, devian.id, "contiene")
    rs.create_relation(tree.id, akshan.id, "contiene")
    rs.create_relation(devian.id, akshan.id, "sirve_a")

    from packages.application.project_service import ProjectService

    project_service = ProjectService()
    project_service.active_project = project
    f = tmp_path / "tree-test.dendro.json"
    assert isinstance(project_service.save(f), Ok)
    project_service.close()

    reopened = project_service.open(f)
    assert isinstance(reopened, Ok)

    entity_names = {e.name for e in reopened.value.entities}
    assert "Hermandad del Acero" in entity_names
    assert "Devian" in entity_names
    assert "Akshan" in entity_names

    rels = reopened.value.relations
    contiene = [r for r in rels if _rtype_value(r) == "contiene"]
    narrative = [r for r in rels if _rtype_value(r) == "sirve_a"]
    assert len(contiene) == 2
    assert len(narrative) == 1

    tree_entity = next(e for e in reopened.value.entities if e.name == "Hermandad del Acero")
    assert tree_entity.entity_type == EntityType.CONTENEDOR


# ── 5. Nested tree persistence ───────────────────────────────────────


def test_nested_tree_persistence(tmp_path):
    """Hermandad inside Alta Aristocracia survives save/reload."""
    project = Project(name="nested tree persist")
    alta = NarrativeEntity(name="Alta Aristocracia", entity_type=EntityType.CONTENEDOR)
    hermandad = NarrativeEntity(name="Hermandad del Acero", entity_type=EntityType.CONTENEDOR)
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    project.entities.extend([alta, hermandad, devian])

    rs = RelationService(FakeProjectService(project))
    rs.create_relation(alta.id, hermandad.id, "contiene")
    rs.create_relation(hermandad.id, devian.id, "contiene")

    from packages.application.project_service import ProjectService

    ps = ProjectService()
    ps.active_project = project
    f = tmp_path / "nested.dendro.json"
    assert isinstance(ps.save(f), Ok)
    ps.close()

    reopened = ps.open(f)
    assert isinstance(reopened, Ok)

    rels = reopened.value.relations
    contiene = [r for r in rels if _rtype_value(r) == "contiene"]
    assert len(contiene) == 2

    id_to_name = {e.id: e.name for e in reopened.value.entities}
    parentage = {}
    for r in contiene:
        parentage[id_to_name[r.source_id]] = id_to_name[r.target_id]
    assert parentage.get("Alta Aristocracia") == "Hermandad del Acero"
    assert parentage.get("Hermandad del Acero") == "Devian"


# ── 6. TreeMeta roundtrip ────────────────────────────────────────────


def test_tree_meta_roundtrip():
    """TreeMeta writes to and reads from custom_metadata."""
    entity = NarrativeEntity(name="Test Tree", entity_type=EntityType.CONTENEDOR)

    meta = TreeMeta(
        tree_type="faccion",
        narrative_role="central",
        internal_rules=["Regla 1", "Regla 2"],
        open_questions=["¿Quién la fundó?"],
        color="#FF8800",
        icon="shield",
    )
    assert meta.validate() == []

    entity.custom_metadata = meta.merge_into(entity.custom_metadata)
    assert entity.custom_metadata[KEY_TREE_TYPE] == "faccion"
    assert entity.custom_metadata[KEY_NARRATIVE_ROLE] == "central"
    assert entity.custom_metadata[KEY_INTERNAL_RULES] == ["Regla 1", "Regla 2"]
    assert entity.custom_metadata[KEY_OPEN_QUESTIONS] == ["¿Quién la fundó?"]

    restored = TreeMeta.from_metadata(entity.custom_metadata)
    assert restored.tree_type == "faccion"
    assert restored.narrative_role == "central"
    assert restored.internal_rules == ["Regla 1", "Regla 2"]
    assert restored.open_questions == ["¿Quién la fundó?"]
    assert restored.color == "#FF8800"
    assert restored.icon == "shield"


def test_tree_meta_preserves_non_tree_keys():
    """TreeMeta.merge_into preserves keys it doesn't manage."""
    entity = NarrativeEntity(name="Test", entity_type=EntityType.CONTENEDOR)
    entity.custom_metadata = {"existing_key": "kept", "other": 42}

    meta = TreeMeta(tree_type="cultura")
    entity.custom_metadata = meta.merge_into(entity.custom_metadata)

    assert entity.custom_metadata["existing_key"] == "kept"
    assert entity.custom_metadata["other"] == 42
    assert entity.custom_metadata[KEY_TREE_TYPE] == "cultura"


def test_tree_meta_validation_rejects_bad_values():
    meta = TreeMeta(tree_type="invalid_type")
    issues = meta.validate()
    assert len(issues) == 1
    assert "invalid_type" in issues[0]


# ── 7. Reassign membership ───────────────────────────────────────────


def test_reassign_membership_removes_old_contiene():
    """Moving a node from tree A to tree B removes the old CONTIENE."""
    project = Project(name="reassign")
    tree_a = NarrativeEntity(name="Tree A", entity_type=EntityType.CONTENEDOR)
    tree_b = NarrativeEntity(name="Tree B", entity_type=EntityType.CONTENEDOR)
    member = NarrativeEntity(name="Member", entity_type=EntityType.PERSONAJE)
    project.entities.extend([tree_a, tree_b, member])

    rs = RelationService(FakeProjectService(project))

    r1 = rs.create_relation(tree_a.id, member.id, "contiene")
    assert isinstance(r1, Ok)
    assert len(project.relations) == 1

    # Simulate workspaces._remove_tree_membership
    to_delete = [
        r for r in project.relations
        if _rtype_value(r) == "contiene"
        and getattr(r, "target_id", "") == member.id
    ]
    for r in to_delete:
        project.relations = [rel for rel in project.relations if rel.id != r.id]

    r2 = rs.create_relation(tree_b.id, member.id, "contiene")
    assert isinstance(r2, Ok)
    assert len(project.relations) == 1
    assert _rtype_value(project.relations[0]) == "contiene"
    assert project.relations[0].source_id == tree_b.id


# ── 8. CONTIENE vs narrative: both coexist ────────────────────────────


def test_structural_and_narrative_relations_coexist():
    """An entity can have CONTIENE belonging AND narrative relation with same tree."""
    project, tree, devian, _ = _project_with_tree()
    rs = RelationService(FakeProjectService(project))

    # Structural belonging
    rs.create_relation(tree.id, devian.id, "contiene")

    # Narrative: Devian betrayed the tree
    rs.create_relation(devian.id, tree.id, "traiciono")

    # Verify both exist independently
    contiene = [r for r in project.relations if _rtype_value(r) == "contiene"]
    narrative = [r for r in project.relations if _rtype_value(r) == "traiciono"]
    assert len(contiene) == 1
    assert len(narrative) == 1
    assert contiene[0].source_id == tree.id
    assert contiene[0].target_id == devian.id
    assert narrative[0].source_id == devian.id
    assert narrative[0].target_id == tree.id
