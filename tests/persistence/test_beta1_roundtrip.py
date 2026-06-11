"""BETA1-B04: Creation graph persistence round-trip."""
from __future__ import annotations

from packages.application.project_service import ProjectService
from packages.domain.result import Ok
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.layer_controller import LayerController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController


def _create_entity(ec: EntityController, name: str, *, kind: str = "nota", layer_ids=None) -> str:
    result = ec.create(
        {
            "name": name,
            "entity_type": kind,
            "brief_description": "",
            "canon_state": "borrador",
            "layer_ids": list(layer_ids or []),
        }
    )
    assert isinstance(result, Ok), getattr(result, "error", "")
    return str(result.value.id)


def test_beta1_creation_graph_roundtrip_preserves_rings_nodes_branches_and_relations(tmp_path):
    ps = ProjectService()
    created = ps.create("BETA1 roundtrip")
    assert isinstance(created, Ok)
    ps.active_project.worldbuilding_active = True

    lc = LayerController(ps)
    ec = EntityController(ps)
    rc = RelationController(ps)

    ring_a = lc.create({"name": "Anillo A", "description": "Base", "order": 1})
    ring_b = lc.create({"name": "Anillo B", "description": "Consecuencia", "order": 2})
    assert isinstance(ring_a, Ok)
    assert isinstance(ring_b, Ok)
    ring_a_id = str(ring_a.value.id)
    ring_b_id = str(ring_b.value.id)
    lc.update(ring_a_id, {"metadata": {"causal_rank": "1"}})
    lc.update(ring_b_id, {"metadata": {"causal_rank": "2"}})

    branch = _create_entity(ec, "Rama Persistente", kind="contenedor", layer_ids=[ring_a_id])
    leaf_a = _create_entity(ec, "Hoja A", layer_ids=[ring_a_id])
    leaf_b = _create_entity(ec, "Hoja B", layer_ids=[ring_b_id])

    contains = rc.create(branch, leaf_a, "contiene", {})
    causal = rc.create(leaf_a, leaf_b, "deriva_de", {"description": "A causa B"})
    assert isinstance(contains, Ok)
    assert isinstance(causal, Ok)

    project_path = tmp_path / "beta1_roundtrip.json"
    saved = ps.save(project_path)
    assert isinstance(saved, Ok)
    ps.close()

    reopened = ProjectService()
    loaded = reopened.open(project_path)
    assert isinstance(loaded, Ok)
    project = reopened.active_project

    layers = {layer.name: layer for layer in project.world_layers}
    assert layers["Anillo A"].metadata.get("causal_rank") == "1"
    assert layers["Anillo B"].metadata.get("causal_rank") == "2"
    assert project.worldbuilding_active is True

    entities = {entity.name: entity for entity in project.entities}
    assert set(entities) >= {"Rama Persistente", "Hoja A", "Hoja B"}
    assert entities["Rama Persistente"].entity_type.value == "contenedor"
    assert ring_a_id in [str(value) for value in entities["Hoja A"].layer_ids]
    assert ring_b_id in [str(value) for value in entities["Hoja B"].layer_ids]

    relation_pairs = {(rel.source_id, rel.target_id, rel.relation_type.value) for rel in project.relations}
    assert (branch, leaf_a, "contiene") in relation_pairs
    assert (leaf_a, leaf_b, "deriva_de") in relation_pairs


def test_beta1_empty_project_roundtrip_opens_without_graph_data_loss(tmp_path):
    ps = ProjectService()
    created = ps.create("BETA1 empty")
    assert isinstance(created, Ok)
    ps.active_project.world_layers = []
    ps.active_project.entities = []
    ps.active_project.relations = []

    project_path = tmp_path / "beta1_empty.json"
    saved = ps.save(project_path)
    assert isinstance(saved, Ok)

    reopened = ProjectService()
    loaded = reopened.open(project_path)
    assert isinstance(loaded, Ok)
    assert reopened.active_project.world_layers == []
    assert reopened.active_project.entities == []
    assert reopened.active_project.relations == []
