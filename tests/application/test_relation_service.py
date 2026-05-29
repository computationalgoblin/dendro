"""Tests for B04-T03: RelationService."""

from pathlib import Path

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import (
    CanonState,
    EntityType,
    NarrativeEntity,
)
from packages.domain.relation import (
    NarrativeRelation,
    RelationType,
)
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup(tmp_path: Path) -> tuple[RelationService, EntityService]:
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test World")
    es = EntityService(project_service=ps, store=store)
    svc = RelationService(project_service=ps, store=store)
    svc._current_path = tmp_path / "proj.json"
    return svc, es


class TestCreateRelation:
    def test_create(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "localizacion"}).value

        result = svc.create_relation(
            source_id=e1.id, target_id=e2.id,
            relation_type=RelationType.ES_ALIADO_DE,
        )
        assert isinstance(result, Ok)
        assert result.value.relation_type == RelationType.ES_ALIADO_DE

    def test_create_nonexistent_source(self, tmp_path: Path):
        svc, _ = _setup(tmp_path)
        result = svc.create_relation(source_id="nonexistent", target_id="nonexistent2")
        assert isinstance(result, Error)

    def test_create_no_project(self):
        store = ProjectStore()
        ps = ProjectService(store=store)
        svc = RelationService(project_service=ps, store=store)
        result = svc.create_relation(source_id="a", target_id="b")
        assert isinstance(result, Error)


class TestGetRelations:
    def test_get_by_id(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        r = svc.create_relation(e1.id, e2.id).value

        result = svc.get_by_id(r.id)
        assert isinstance(result, Ok)
        assert result.value.id == r.id

    def test_get_incoming(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)

        incoming = svc.get_incoming(e2.id)
        assert isinstance(incoming, Ok)
        assert len(incoming.value) == 1

    def test_get_outgoing(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)

        outgoing = svc.get_outgoing(e1.id)
        assert isinstance(outgoing, Ok)
        assert len(outgoing.value) == 1

    def test_get_between(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)

        between = svc.get_between(e1.id, e2.id)
        assert isinstance(between, Ok)
        assert len(between.value) == 1

    def test_get_neighborhood(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        e3 = es.create_entity({"name": "C", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)
        svc.create_relation(e3.id, e1.id)

        hood = svc.get_neighborhood(e1.id)
        assert isinstance(hood, Ok)
        assert len(hood.value) == 2


class TestSimplePaths:
    def test_direct_path(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)

        paths = svc.find_simple_paths(e1.id, e2.id)
        assert isinstance(paths, Ok)
        assert len(paths.value) == 1
        assert len(paths.value[0]) == 1

    def test_no_path(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value

        paths = svc.find_simple_paths(e1.id, e2.id)
        assert isinstance(paths, Ok)
        assert len(paths.value) == 0

    def test_two_hop_path(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        e3 = es.create_entity({"name": "C", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)
        svc.create_relation(e2.id, e3.id)

        paths = svc.find_simple_paths(e1.id, e3.id)
        assert isinstance(paths, Ok)
        assert len(paths.value) == 1
        assert len(paths.value[0]) == 2


class TestFilters:
    def test_filter_by_relation_type(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id, relation_type=RelationType.ES_ENEMIGO_DE)
        svc.create_relation(e1.id, e2.id, relation_type=RelationType.ES_ALIADO_DE)

        r = svc.filter_by_relation_type(RelationType.ES_ENEMIGO_DE)
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_canon_state(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        r = svc.create_relation(e1.id, e2.id).value
        svc.archive_relation(r.id)

        archived = svc.filter_by_canon_state(CanonState.ARCHIVADO)
        assert isinstance(archived, Ok)
        assert len(archived.value) == 1


class TestMutateOperations:
    def test_add_remove_tag(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        r = svc.create_relation(e1.id, e2.id).value

        svc.add_tag(r.id, "important")
        assert "important" in r.tags

        svc.remove_tag(r.id, "important")
        assert "important" not in r.tags

    def test_change_canon_state(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        r = svc.create_relation(e1.id, e2.id).value

        result = svc.change_canon_state(r.id, CanonState.CANONICO)
        assert isinstance(result, Ok)
        assert result.value.canon_state == CanonState.CANONICO


class TestBrokenInactive:
    def test_get_broken_relations(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        # Bypass referential integrity check by adding directly
        svc.project_service.active_project.relations.append(
            NarrativeRelation(source_id=e1.id, target_id="nonexistent")
        )

        broken = svc.get_broken_relations()
        assert isinstance(broken, Ok)
        assert len(broken.value) == 1

    def test_no_broken_when_all_valid(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)

        broken = svc.get_broken_relations()
        assert isinstance(broken, Ok)
        assert len(broken.value) == 0

    def test_get_inactive_relations(self, tmp_path: Path):
        svc, es = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id)
        es.archive_entity(e1.id)

        inactive = svc.get_inactive_relations()
        assert isinstance(inactive, Ok)
        assert len(inactive.value) == 1


class TestPersistenceRoundtrip:
    def test_save_load_with_relations(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="RelTest")

        es = EntityService(project_service=ps, store=store)
        svc = RelationService(project_service=ps, store=store)

        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        svc.create_relation(e1.id, e2.id, relation_type=RelationType.CONTROLA)

        path = tmp_path / "reltest.json"
        ps.save(path)
        ps.close()
        ps.open(path)

        svc2 = RelationService(project_service=ps, store=store)
        all_r = svc2.list_all()
        assert isinstance(all_r, Ok)
        assert len(all_r.value) == 1
        assert all_r.value[0].relation_type == RelationType.CONTROLA
