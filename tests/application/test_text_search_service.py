"""Tests for B06-T02: TextSearchService."""

from pathlib import Path

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.application.text_search_service import SearchResults, TextSearchService
from packages.domain.entity import EntityType
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup(tmp_path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="SearchTest")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    ts = TextSearchService(entity_service=es, relation_service=rs)
    return ts, es, rs


class TestSearchEntities:
    def test_name_match(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        es.create_entity({"name": "Eldrin the Wise", "entity_type": "personaje"})
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})

        r = ts.search_entities("eldrin")
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "Eldrin the Wise"

    def test_case_insensitive(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        es.create_entity({"name": "Dragon", "entity_type": "criatura"})

        r1 = ts.search_entities("dragon")
        r2 = ts.search_entities("DRAGON")
        assert len(r1.value) == len(r2.value)

    def test_description_match(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        es.create_entity({"name": "X", "entity_type": "nota",
                          "extended_description": "Lorem ipsum dolor sit amet"})

        r = ts.search_entities("ipsum")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_tag_match(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e = es.create_entity({"name": "X", "entity_type": "nota"}).value
        es.add_tag(e.id, "wizard")

        r = ts.search_entities("wizard")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_alias_match(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e = es.create_entity({"name": "Eldrin", "entity_type": "personaje"}).value
        e.aliases = ["The Grey"]

        r = ts.search_entities("grey")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_private_notes_included_by_default(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e = es.create_entity({"name": "X", "entity_type": "nota"}).value
        e.private_notes = "Secret weakness: cats"

        r = ts.search_entities("weakness")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_private_notes_excluded(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e = es.create_entity({"name": "X", "entity_type": "nota"}).value
        e.private_notes = "Secret weakness: cats"

        r = ts.search_entities("weakness", include_private=False)
        assert isinstance(r, Ok)
        assert len(r.value) == 0

    def test_no_results(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        es.create_entity({"name": "A", "entity_type": "nota"})

        r = ts.search_entities("xyzzy_nonexistent")
        assert isinstance(r, Ok)
        assert len(r.value) == 0

    def test_relevance_order(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e1 = es.create_entity({"name": "Dragon", "entity_type": "criatura"}).value
        e2 = es.create_entity({"name": "Wizard", "entity_type": "personaje",
                               "extended_description": "The wizard fought a dragon"}).value

        r = ts.search_entities("dragon")
        names = [e.name for e in r.value]
        assert names[0] == "Dragon"  # name match before description match


class TestSearchByField:
    def test_valid_field(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        es.create_entity({"name": "Eldrin", "entity_type": "personaje"})

        r = ts.search_by_field("eldrin", "name")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_invalid_field(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        r = ts.search_by_field("test", "invalid_field")
        assert isinstance(r, Error)
        assert "Unsupported" in r.error

    def test_search_in_tags(self, tmp_path: Path):
        ts, es, _ = _setup(tmp_path)
        e = es.create_entity({"name": "X", "entity_type": "nota"}).value
        es.add_tag(e.id, "dragon")

        r = ts.search_by_field("dragon", "tags")
        assert isinstance(r, Ok)
        assert len(r.value) == 1


class TestSearchRelations:
    def test_description_match(self, tmp_path: Path):
        ts, es, rs = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(e1.id, e2.id).value
        rel.description = "Strong alliance"

        r = ts.search_relations("alliance")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_validity_conditions_match(self, tmp_path: Path):
        ts, es, rs = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(e1.id, e2.id).value
        rel.validity_conditions = ["treaty must hold", "at dawn"]

        r = ts.search_relations("treaty")
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_no_results(self, tmp_path: Path):
        ts, es, rs = _setup(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rs.create_relation(e1.id, e2.id)

        r = ts.search_relations("nonexistent_term")
        assert isinstance(r, Ok)
        assert len(r.value) == 0


class TestSearchAll:
    def test_combined_results(self, tmp_path: Path):
        ts, es, rs = _setup(tmp_path)
        es.create_entity({"name": "Dragon", "entity_type": "criatura"})
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(e1.id, e2.id).value
        rel.description = "dragon alliance"

        r = ts.search_all("dragon")
        assert isinstance(r, Ok)
        assert len(r.value.entities) == 1
        assert len(r.value.relations) == 1
        assert r.value.total_hits == 2
