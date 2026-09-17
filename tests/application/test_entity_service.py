"""Tests for B03-T03: EntityService — application-layer entity operations.

Covers all 22 methods plus error paths and the modify→save→reload cycle.
"""

from pathlib import Path

from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.domain.entity import (
    CanonState,
    EntityType,
    NarrativeEntity,
    VisibilityState,
)
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup(tmp_path: Path) -> EntityService:
    """Create a ready EntityService with an active project and a file path."""
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test World")
    svc = EntityService(project_service=ps, store=store)
    svc._current_path = tmp_path / "proj.json"
    return svc


# ---------------------------------------------------------------------------
# create_entity
# ---------------------------------------------------------------------------


class TestCreateEntity:
    def test_create_with_name_and_type(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.create_entity({"name": "Eldrin", "entity_type": "personaje"})
        assert isinstance(result, Ok)
        assert result.value.name == "Eldrin"
        assert result.value.entity_type == EntityType.PERSONAJE

    def test_create_defaults(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.create_entity({"name": "X", "entity_type": "nota"})
        assert isinstance(result, Ok)
        assert result.value.canon_state == CanonState.CANONICO
        assert result.value.visibility_state == VisibilityState.VISIBLE_USUARIO

    def test_create_empty_name_fails(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.create_entity({"name": "", "entity_type": "personaje"})
        assert isinstance(result, Error)
        assert "nombre" in result.error.lower()  # BETA-FIX-06: error en español

    def test_create_no_active_project(self):
        store = ProjectStore()
        ps = ProjectService(store=store)
        svc = EntityService(project_service=ps, store=store)
        result = svc.create_entity({"name": "Ghost", "entity_type": "nota"})
        assert isinstance(result, Error)
        assert "No active project" in result.error

    def test_create_adds_to_project(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "E1", "entity_type": "personaje"})
        assert len(svc.project_service.active_project.entities) == 1


# ---------------------------------------------------------------------------
# update_entity
# ---------------------------------------------------------------------------


class TestUpdateEntity:
    def test_update_modifies_fields(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Old", "entity_type": "nota"}).value
        result = svc.update_entity(e.id, {"name": "New", "brief_description": "Desc"})
        assert isinstance(result, Ok)
        assert result.value.name == "New"
        assert result.value.brief_description == "Desc"

    def test_update_nonexistent(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.update_entity("nonexistent", {"name": "X"})
        assert isinstance(result, Error)
        assert "not found" in result.error.lower()

    def test_update_no_active_project(self):
        store = ProjectStore()
        ps = ProjectService(store=store)
        svc = EntityService(project_service=ps, store=store)
        result = svc.update_entity("id", {"name": "X"})
        assert isinstance(result, Error)


# ---------------------------------------------------------------------------
# archive / restore / controlled_delete
# ---------------------------------------------------------------------------


class TestArchive:
    def test_archive_sets_canon_state(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "ToArchive", "entity_type": "nota"}).value
        result = svc.archive_entity(e.id)
        assert isinstance(result, Ok)

        loaded = svc.get_by_id(e.id)
        assert loaded.value.canon_state == CanonState.ARCHIVADO

    def test_archive_nonexistent(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.archive_entity("nonexistent")
        assert isinstance(result, Error)

    def test_restore(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "RestoreMe", "entity_type": "nota"}).value
        svc.archive_entity(e.id)
        result = svc.restore_entity(e.id)
        assert isinstance(result, Ok)
        assert result.value.canon_state == CanonState.CANONICO

    def test_restore_non_archived_errors(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Active", "entity_type": "nota"}).value
        result = svc.restore_entity(e.id)
        assert isinstance(result, Error)
        assert "not archived" in result.error.lower()

    def test_controlled_delete(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Controlled", "entity_type": "nota"}).value
        result = svc.controlled_delete_entity(e.id)
        assert isinstance(result, Ok)

        loaded = svc.get_by_id(e.id)
        assert loaded.value.canon_state == CanonState.ARCHIVADO


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    def test_found(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Target", "entity_type": "personaje"}).value
        result = svc.get_by_id(e.id)
        assert isinstance(result, Ok)
        assert result.value.name == "Target"

    def test_not_found(self, tmp_path: Path):
        svc = _setup(tmp_path)
        result = svc.get_by_id("nonexistent")
        assert isinstance(result, Error)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_filter_by_type(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "P1", "entity_type": "personaje"})
        svc.create_entity({"name": "L1", "entity_type": "localizacion"})

        r = svc.filter_by_type(EntityType.PERSONAJE)
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "P1"

    def test_filter_by_type_string(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "L1", "entity_type": "localizacion"})
        r = svc.filter_by_type("localizacion")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_canon_state(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Arch", "entity_type": "nota"}).value
        svc.archive_entity(e.id)

        r = svc.filter_by_canon_state(CanonState.ARCHIVADO)
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_visibility_state(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "V", "entity_type": "nota"})
        r = svc.filter_by_visibility_state("visible_usuario")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_tag(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e1 = svc.create_entity({"name": "Tagged", "entity_type": "nota"}).value
        svc.add_tag(e1.id, "wizard")
        svc.create_entity({"name": "Untagged", "entity_type": "nota"})

        r = svc.filter_by_tag("wizard")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_domain(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "D", "entity_type": "nota"}).value
        svc.update_entity(e.id, {"domain": "fantasy"})
        svc.create_entity({"name": "D2", "entity_type": "nota"})

        r = svc.filter_by_domain("fantasy")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_layer(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Layered", "entity_type": "nota"}).value
        svc.update_entity(e.id, {"custom_metadata": {}})  # no layer field in update
        # Set layer via direct access
        e.layers = ["main"]
        svc.create_entity({"name": "NoLayer", "entity_type": "nota"})

        r = svc.filter_by_layer("main")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_archived(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Arch", "entity_type": "nota"}).value
        svc.archive_entity(e.id)
        svc.create_entity({"name": "Active", "entity_type": "nota"})

        r = svc.filter_by_archived(True)
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "Arch"

        r2 = svc.filter_by_archived(False)
        assert isinstance(r2, Ok)
        assert len(r2.value) == 1
        assert r2.value[0].name == "Active"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_by_name(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "Eldrin", "entity_type": "personaje"})
        svc.create_entity({"name": "Gandalf", "entity_type": "personaje"})

        r = svc.search_by_name("eld")
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "Eldrin"

    def test_search_by_alias(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "Eldrin", "entity_type": "personaje"}).value
        svc.add_tag(e.id, "placeholder")
        e.aliases = ["The Wise", "Old Man"]

        r = svc.search_by_alias("wise")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_search_combined(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "Eldrin", "entity_type": "personaje"})
        e = svc.create_entity({"name": "Other", "entity_type": "personaje"}).value
        e.aliases = ["Eldrin the Younger"]

        r = svc.search("eldrin")
        assert isinstance(r, Ok)
        assert len(r.value) == 2


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestSorting:
    def test_sort_by_name(self, tmp_path: Path):
        svc = _setup(tmp_path)
        svc.create_entity({"name": "Zeta", "entity_type": "nota"})
        svc.create_entity({"name": "Alpha", "entity_type": "nota"})
        svc.create_entity({"name": "Beta", "entity_type": "nota"})

        all_r = svc.list_all()
        sorted_entities = svc.sort_by_name(all_r.value)
        assert sorted_entities[0].name == "Alpha"
        assert sorted_entities[2].name == "Zeta"

    def test_sort_by_updated_at(self, tmp_path: Path):
        import time

        svc = _setup(tmp_path)
        svc.create_entity({"name": "First", "entity_type": "nota"})
        time.sleep(0.01)
        svc.create_entity({"name": "Second", "entity_type": "nota"})

        all_r = svc.list_all()
        sorted_entities = svc.sort_by_updated_at(all_r.value)
        assert sorted_entities[0].name == "Second"  # most recent first


# ---------------------------------------------------------------------------
# State operations
# ---------------------------------------------------------------------------


class TestStateOperations:
    def test_change_canon_state(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "CS", "entity_type": "nota"}).value
        result = svc.change_canon_state(e.id, CanonState.CANONICO)
        assert isinstance(result, Ok)
        assert result.value.canon_state == CanonState.CANONICO

    def test_change_canon_state_string(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "CS2", "entity_type": "nota"}).value
        result = svc.change_canon_state(e.id, "hipotesis")
        assert isinstance(result, Ok)
        assert result.value.canon_state == CanonState.HIPOTESIS

    def test_change_visibility_state(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "VS", "entity_type": "nota"}).value
        result = svc.change_visibility_state(e.id, "revelado")
        assert isinstance(result, Ok)
        assert result.value.visibility_state == VisibilityState.REVELADO

    def test_add_tag(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "T", "entity_type": "nota"}).value
        result = svc.add_tag(e.id, "tag1")
        assert isinstance(result, Ok)
        assert "tag1" in result.value.tags

    def test_add_tag_idempotent(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "T", "entity_type": "nota"}).value
        svc.add_tag(e.id, "tag1")
        svc.add_tag(e.id, "tag1")
        assert e.tags.count("tag1") == 1

    def test_remove_tag(self, tmp_path: Path):
        svc = _setup(tmp_path)
        e = svc.create_entity({"name": "T", "entity_type": "nota"}).value
        svc.add_tag(e.id, "removable")
        result = svc.remove_tag(e.id, "removable")
        assert isinstance(result, Ok)
        assert "removable" not in result.value.tags


# ---------------------------------------------------------------------------
# Persistence roundtrip
# ---------------------------------------------------------------------------


class TestPersistenceRoundtrip:
    def test_create_archive_reload(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="CycleTest")

        path = tmp_path / "cycle.json"
        ps.save(path)

        svc = EntityService(project_service=ps, store=store)
        svc._current_path = path

        e = svc.create_entity({"name": "Eldrin", "entity_type": "personaje"}).value
        svc.archive_entity(e.id)
        svc.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        ps.save(path)

        # Reopen
        ps.close()
        ps.open(path)

        svc2 = EntityService(project_service=ps, store=store)
        all_r = svc2.list_all()
        assert len(all_r.value) == 2

        active = svc2.filter_by_archived(False)
        assert len(active.value) == 1
        assert active.value[0].name == "Gandalf"

        archived = svc2.filter_by_archived(True)
        assert len(archived.value) == 1
        assert archived.value[0].name == "Eldrin"
