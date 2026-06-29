"""BETA1-L01 — índices derivados O(1) en Project.

Caché de solo lectura (id→entidad, id→relación, adyacencia) invalidada por la
revisión que bump-ea ``touch()``, con respaldo por tamaño. No es una segunda
fuente de verdad: las listas siguen mandando."""

from __future__ import annotations

from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation


def _entity(name: str) -> NarrativeEntity:
    return NarrativeEntity(name=name)


def test_entity_and_relation_by_id_are_found():
    a, b = _entity("A"), _entity("B")
    r = NarrativeRelation(source_id=a.id, target_id=b.id)
    proj = Project(entities=[a, b], relations=[r])
    assert proj.entity_by_id(a.id) is a
    assert proj.entity_by_id(b.id) is b
    assert proj.entity_by_id("missing") is None
    assert proj.relation_by_id(r.id) is r
    assert proj.relation_by_id("missing") is None


def test_relations_for_returns_incident_relations():
    a, b, c = _entity("A"), _entity("B"), _entity("C")
    r_ab = NarrativeRelation(source_id=a.id, target_id=b.id)
    r_ca = NarrativeRelation(source_id=c.id, target_id=a.id)
    proj = Project(entities=[a, b, c], relations=[r_ab, r_ca])
    nbrs = proj.relations_for(a.id)
    assert set(id(r) for r in nbrs) == {id(r_ab), id(r_ca)}  # origen y destino
    assert proj.relations_for(b.id) == [r_ab]
    assert proj.relations_for("missing") == []


def test_self_loop_listed_once():
    a = _entity("A")
    loop = NarrativeRelation(source_id=a.id, target_id=a.id)
    proj = Project(entities=[a], relations=[loop])
    assert proj.relations_for(a.id) == [loop]  # no duplicado por origen==destino


def test_relations_for_returns_fresh_list():
    a, b = _entity("A"), _entity("B")
    r = NarrativeRelation(source_id=a.id, target_id=b.id)
    proj = Project(entities=[a, b], relations=[r])
    out = proj.relations_for(a.id)
    out.append("intruso")
    assert proj.relations_for(a.id) == [r]  # mutar la copia no toca el índice


def test_index_invalidates_on_touch_after_append():
    a = _entity("A")
    proj = Project(entities=[a], relations=[])
    assert proj.entity_by_id(a.id) is a  # construye índice
    b = _entity("B")
    proj.entities.append(b)
    proj.touch()  # patrón real de los servicios
    assert proj.entity_by_id(b.id) is b  # índice reconstruido


def test_index_invalidates_by_size_backstop_without_touch():
    a = _entity("A")
    proj = Project(entities=[a], relations=[])
    assert proj.entity_by_id(a.id) is a
    b = _entity("B")
    proj.entities.append(b)  # SIN touch: el respaldo por tamaño lo detecta
    assert proj.entity_by_id(b.id) is b


def test_index_reflects_removal():
    a, b = _entity("A"), _entity("B")
    proj = Project(entities=[a, b], relations=[])
    assert proj.entity_by_id(b.id) is b
    proj.entities.remove(b)
    proj.touch()
    assert proj.entity_by_id(b.id) is None


def test_in_place_edit_keeps_same_object_in_index():
    a = _entity("A")
    proj = Project(entities=[a], relations=[])
    assert proj.entity_by_id(a.id) is a
    a.name = "A renombrada"  # edición in situ: misma referencia
    proj.touch()
    assert proj.entity_by_id(a.id) is a
    assert proj.entity_by_id(a.id).name == "A renombrada"
