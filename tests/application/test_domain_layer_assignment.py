"""Tests for B10-T03: Domain and layer assignment on entities and relations,
plus QueryService domain_id/layer_id filters.

PA04 eliminó ``AdvancedConfigService`` (Gen B); sus tests se retiraron. La
asignación de dominios/capas y los filtros de QueryService siguen vivos.
"""

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.relation_service import RelationService
from packages.domain.relation import RelationType
from packages.domain.result import Error, Ok


def _setup():
    """Create a project with entity service, relation service, and query service.

    Siembra las 16 capas por defecto: ``ProjectService.create`` construye un
    ``Project`` con ``world_layers=[]`` (las capas estándar solo las añade la
    migración v6→v7 al cargar proyectos viejos), y estos tests asignan capas por
    su id estándar (``layer_geografia``…). Sin sembrarlas, ``assign_layer``
    fallaría con "world layer not found".
    """
    from packages.domain.world_layer import default_world_layers

    ps = ProjectService()
    ps.create("Test World")
    ps.active_project.world_layers = default_world_layers()
    es = EntityService(ps, ps.store)
    rs = RelationService(ps, ps.store)
    qs = QueryService(es, rs, None)  # source_service not needed for these tests
    return ps, es, rs, qs


# ══════════════════════════════════════════════════════════════════
# EntityService — domains
# ══════════════════════════════════════════════════════════════════

class TestEntityDomainAssignment:
    def test_assign_domain(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        entity = es.list_all().value[0]

        result = es.assign_domain(entity.id, "mundo")
        assert isinstance(result, Ok)
        assert "mundo" in result.value.domain_ids

    def test_assign_domain_invalid(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        entity = es.list_all().value[0]

        result = es.assign_domain(entity.id, "invalido")
        assert isinstance(result, Error)
        assert "Invalid domain" in result.error

    def test_remove_domain(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        entity = es.list_all().value[0]
        es.assign_domain(entity.id, "mundo")

        result = es.remove_domain(entity.id, "mundo")
        assert isinstance(result, Ok)
        assert "mundo" not in result.value.domain_ids

    def test_remove_domain_idempotent(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        entity = es.list_all().value[0]
        # Removing a domain that's not assigned should not error
        result = es.remove_domain(entity.id, "mundo")
        assert isinstance(result, Ok)

    def test_get_by_domain(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        es.create_entity({"name": "Mordor", "entity_type": "lugar"})
        entities = es.list_all().value
        gandalf = entities[0]

        es.assign_domain(gandalf.id, "historia")

        result = es.get_by_domain("historia")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert result.value[0].name == "Gandalf"

    def test_assign_duplicate_domain_noop(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        entity = es.list_all().value[0]

        es.assign_domain(entity.id, "mundo")
        es.assign_domain(entity.id, "mundo")  # duplicate
        assert entity.domain_ids.count("mundo") == 1


# ══════════════════════════════════════════════════════════════════
# EntityService — layers
# ══════════════════════════════════════════════════════════════════

class TestEntityLayerAssignment:
    def test_assign_layer(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Tierra Media", "entity_type": "region"})
        entity = es.list_all().value[0]

        result = es.assign_layer(entity.id, "layer_geografia")
        assert isinstance(result, Ok)
        assert "layer_geografia" in result.value.layer_ids

    def test_assign_layer_invalid_id(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Tierra Media", "entity_type": "region"})
        entity = es.list_all().value[0]

        result = es.assign_layer(entity.id, "no_existe")
        assert isinstance(result, Error)

    def test_assign_layer_hidden(self):
        ps, es, rs, qs = _setup()
        ps.active_project.world_layers[0].is_visible = False  # hide first layer
        es.create_entity({"name": "Test", "entity_type": "concepto"})
        entity = es.list_all().value[0]

        result = es.assign_layer(entity.id, "layer_premisa")
        assert isinstance(result, Error)
        assert "hidden" in result.error.lower()

    def test_remove_layer(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Tierra Media", "entity_type": "region"})
        entity = es.list_all().value[0]
        es.assign_layer(entity.id, "layer_geografia")

        result = es.remove_layer(entity.id, "layer_geografia")
        assert isinstance(result, Ok)
        assert "layer_geografia" not in result.value.layer_ids

    def test_remove_layer_idempotent(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Test", "entity_type": "concepto"})
        entity = es.list_all().value[0]

        result = es.remove_layer(entity.id, "layer_geografia")
        assert isinstance(result, Ok)

    def test_get_by_layer(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Moria", "entity_type": "lugar"})
        es.create_entity({"name": "Gondor", "entity_type": "reino"})
        entities = es.list_all().value

        es.assign_layer(entities[0].id, "layer_geografia")

        result = es.get_by_layer("layer_geografia")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert result.value[0].name == "Moria"


# ══════════════════════════════════════════════════════════════════
# RelationService — layers
# ══════════════════════════════════════════════════════════════════

class TestRelationLayerAssignment:
    def test_assign_layer_to_relation(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "Gandalf", "entity_type": "personaje"})
        es.create_entity({"name": "Frodo", "entity_type": "personaje"})
        entities = es.list_all().value
        rs.create_relation(
            source_id=entities[0].id,
            target_id=entities[1].id,
            relation_type=RelationType.CONOCE,
        )
        relation = rs.list_all().value[0]

        result = rs.assign_layer(relation.id, "layer_historia")
        assert isinstance(result, Ok)
        assert "layer_historia" in result.value.layer_ids

    def test_assign_layer_to_relation_hidden(self):
        ps, es, rs, qs = _setup()
        ps.active_project.world_layers[0].is_visible = False
        es.create_entity({"name": "A", "entity_type": "personaje"})
        es.create_entity({"name": "B", "entity_type": "personaje"})
        entities = es.list_all().value
        rs.create_relation(
            source_id=entities[0].id, target_id=entities[1].id,
            relation_type="esta_relacionado_con",
        )
        relation = rs.list_all().value[0]

        result = rs.assign_layer(relation.id, "layer_premisa")
        assert isinstance(result, Error)
        assert "hidden" in result.error.lower()

    def test_remove_layer_from_relation(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "A", "entity_type": "personaje"})
        es.create_entity({"name": "B", "entity_type": "personaje"})
        entities = es.list_all().value
        rs.create_relation(
            source_id=entities[0].id, target_id=entities[1].id,
            relation_type="esta_relacionado_con",
        )
        relation = rs.list_all().value[0]
        rs.assign_layer(relation.id, "layer_historia")

        result = rs.remove_layer(relation.id, "layer_historia")
        assert isinstance(result, Ok)
        assert "layer_historia" not in result.value.layer_ids

    def test_get_relations_by_layer(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "A", "entity_type": "personaje"})
        es.create_entity({"name": "B", "entity_type": "personaje"})
        entities = es.list_all().value
        rs.create_relation(
            source_id=entities[0].id, target_id=entities[1].id,
            relation_type="esta_relacionado_con",
        )
        relation = rs.list_all().value[0]
        rs.assign_layer(relation.id, "layer_narrativa")

        result = rs.get_by_layer("layer_narrativa")
        assert isinstance(result, Ok)
        assert len(result.value) == 1


# ══════════════════════════════════════════════════════════════════
# QueryService — domain_id / layer_id filters
# ══════════════════════════════════════════════════════════════════

class TestQueryDomainLayerFilters:
    def test_query_by_domain_id(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "A", "entity_type": "personaje"})
        es.create_entity({"name": "B", "entity_type": "personaje"})
        entities = es.list_all().value
        es.assign_domain(entities[0].id, "mundo")

        result = qs.query(domain_id="mundo")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert result.value[0].name == "A"

    def test_query_by_layer_id(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "M", "entity_type": "lugar"})
        es.create_entity({"name": "N", "entity_type": "lugar"})
        entities = es.list_all().value
        es.assign_layer(entities[0].id, "layer_geografia")

        result = qs.query(layer_id="layer_geografia")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert result.value[0].name == "M"

    def test_query_domain_id_and_layer_id_and(self):
        ps, es, rs, qs = _setup()
        es.create_entity({"name": "X", "entity_type": "lugar"})
        es.create_entity({"name": "Y", "entity_type": "lugar"})
        entities = es.list_all().value

        es.assign_domain(entities[0].id, "mundo")
        es.assign_layer(entities[0].id, "layer_geografia")
        es.assign_domain(entities[1].id, "mundo")
        # Y has domain but not layer

        result = qs.query(domain_id="mundo", layer_id="layer_geografia")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert result.value[0].name == "X"

    def test_legacy_domain_filter_still_works(self):
        ps, es, rs, qs = _setup()
        # Use update_entity to set legacy domain field
        from packages.domain.entity import NarrativeEntity
        e = NarrativeEntity.from_dict(
            {"name": "Legacy", "entity_type": "personaje", "domain": "tierra_media"}
        )
        ps.active_project.entities.append(e)

        result = qs.query(domain="tierra_media")
        assert isinstance(result, Ok)
        assert len(result.value) == 1

    def test_legacy_layer_filter_still_works(self):
        ps, es, rs, qs = _setup()
        from packages.domain.entity import NarrativeEntity
        e = NarrativeEntity.from_dict(
            {"name": "Legacy", "entity_type": "lugar",
             "layers": ["geografia"]}
        )
        ps.active_project.entities.append(e)

        result = qs.query(layer="geografia")
        assert isinstance(result, Ok)
        assert len(result.value) == 1
