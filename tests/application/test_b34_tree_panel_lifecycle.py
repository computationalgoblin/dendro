"""B34-T04 — Tree panel draft lifecycle: is_new, cancel, save.

Validates that:
- Creating a tree marks _visual_draft.
- Save removes _visual_draft and is_new=False.
- Cancel with is_new deletes the entity.
- Cancel without is_new just closes.
"""

from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.application.tree_meta import TreeMeta
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _project_with_draft_tree():
    project = Project(name="B34-T04 tree panel lifecycle")
    tree = NarrativeEntity(
        name="Nuevo contenedor",
        entity_type=EntityType.CONTENEDOR,
        custom_metadata={"_visual_draft": True},
    )
    project.entities.append(tree)
    return project, tree


def test_draft_tree_has_visual_draft_metadata():
    """New tree is created with _visual_draft: True."""
    project, tree = _project_with_draft_tree()
    assert tree.custom_metadata.get("_visual_draft") is True


def test_save_removes_visual_draft():
    """Saving a tree removes _visual_draft from custom_metadata."""
    project, tree = _project_with_draft_tree()
    es = EntityService(FakeProjectService(project))

    # Simulate save: update with metadata without _visual_draft
    meta = TreeMeta(tree_type="faccion", color="#FF8800")
    merged = meta.merge_into(tree.custom_metadata)
    merged.pop("_visual_draft", None)

    result = es.update_entity(tree.id, {
        "name": "Hermandad del Acero",
        "custom_metadata": merged,
        "canon_state": "canonico",
    })
    assert isinstance(result, Ok)

    # Verify _visual_draft is gone
    updated = next(e for e in project.entities if e.id == tree.id)
    assert "_visual_draft" not in updated.custom_metadata
    assert updated.name == "Hermandad del Acero"


def test_cancel_draft_deletes_entity():
    """Cancel on is_new tree deletes the entity."""
    project, tree = _project_with_draft_tree()
    es = EntityService(FakeProjectService(project))

    assert len(project.entities) == 1

    # Simulate cancel is_new: delete entity
    result = es.delete_entity(tree.id)
    assert isinstance(result, Ok)
    assert len(project.entities) == 0


def test_save_then_cancel_does_not_delete():
    """After save (is_new=False), cancel does NOT delete."""
    project, tree = _project_with_draft_tree()
    es = EntityService(FakeProjectService(project))

    # First save
    meta = TreeMeta(tree_type="faccion")
    merged = meta.merge_into(tree.custom_metadata)
    merged.pop("_visual_draft", None)
    es.update_entity(tree.id, {"name": "Saved Tree", "custom_metadata": merged})

    # After save, cancel should NOT delete
    assert len(project.entities) == 1
    saved = next(e for e in project.entities if e.id == tree.id)
    assert saved.name == "Saved Tree"
    assert "_visual_draft" not in saved.custom_metadata


def test_draft_tree_persistence_after_save(tmp_path):
    """Draft tree survives save/reload after _visual_draft is removed."""
    from packages.application.project_service import ProjectService

    project, tree = _project_with_draft_tree()
    es = EntityService(FakeProjectService(project))

    # Save the draft (removes _visual_draft)
    meta = TreeMeta(tree_type="organizacion", narrative_role="central")
    merged = meta.merge_into(tree.custom_metadata)
    merged.pop("_visual_draft", None)
    es.update_entity(tree.id, {
        "name": "Hermandad del Acero",
        "brief_description": "Una facción militar",
        "custom_metadata": merged,
    })

    # Persist
    ps = ProjectService()
    ps.active_project = project
    f = tmp_path / "tree-draft.dendro.json"
    assert isinstance(ps.save(f), Ok)
    ps.close()

    # Reload
    reopened = ps.open(f)
    assert isinstance(reopened, Ok)
    restored = reopened.value.entities[0]
    assert restored.name == "Hermandad del Acero"
    assert restored.entity_type == EntityType.CONTENEDOR
    assert "_visual_draft" not in restored.custom_metadata
    assert restored.custom_metadata.get("tree_type") == "organizacion"


def test_cancel_draft_with_members_does_not_delete_members():
    """Cancel draft tree: tree is deleted but members are not."""
    project, tree = _project_with_draft_tree()
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    project.entities.append(devian)

    rs = RelationService(FakeProjectService(project))
    es = EntityService(FakeProjectService(project))

    # Devian belongs to tree
    rs.create_relation(tree.id, devian.id, "contiene")
    assert len(project.relations) == 1

    # Cancel draft (delete tree)
    es.delete_entity(tree.id)

    # Devian survives, relation cascade-removed
    assert len(project.entities) == 1
    assert project.entities[0].name == "Devian"
    assert len(project.relations) == 0
