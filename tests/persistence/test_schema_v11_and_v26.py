"""Tests dedicados de migraciones sin cobertura propia (BETA1-AUDIT-04).

- v10 → v11: introduce la colección ``import_baskets`` (histórica: el subsistema
  de importación se retiró, pero la migración debe seguir funcionando para que
  los proyectos antiguos carguen).
- v25 → v26: promociona ``birth_year``/``death_year`` desde ``custom_metadata``
  a campos de primera clase de las relaciones.
"""

from __future__ import annotations

from packages.persistence.schema import (
    _apply_migration_v10_to_v11,
    _apply_migration_v25_to_v26,
)


# ── v10 → v11 ────────────────────────────────────────────────────────────────


def _v10_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "schema_version": 10,
        "entities": [{"id": "e1", "name": "Eldrin"}],
    }


def test_v10_to_v11_adds_import_baskets_and_bumps_version():
    migrated = _apply_migration_v10_to_v11(_v10_project())
    assert migrated["import_baskets"] == []
    assert migrated["schema_version"] == 11


def test_v10_to_v11_preserves_existing_data_and_does_not_mutate_input():
    original = _v10_project()
    migrated = _apply_migration_v10_to_v11(original)
    assert migrated["entities"] == [{"id": "e1", "name": "Eldrin"}]
    assert original["schema_version"] == 10
    assert "import_baskets" not in original


def test_v10_to_v11_keeps_preexisting_baskets():
    data = _v10_project()
    data["import_baskets"] = [{"id": "b1"}]
    migrated = _apply_migration_v10_to_v11(data)
    assert migrated["import_baskets"] == [{"id": "b1"}]


# ── v25 → v26 ────────────────────────────────────────────────────────────────


def _v25_project(relations):
    return {
        "id": "p1",
        "name": "Proyecto",
        "schema_version": 25,
        "relations": relations,
    }


def test_v25_to_v26_promotes_temporal_fields_from_metadata():
    data = _v25_project([
        {"id": "r1", "custom_metadata": {"birth_year": "1200", "death_year": 1250}},
    ])
    migrated = _apply_migration_v25_to_v26(data)
    rel = migrated["relations"][0]
    assert rel["birth_year"] == 1200
    assert rel["death_year"] == 1250
    assert migrated["schema_version"] == 26


def test_v25_to_v26_defaults_to_none_without_metadata():
    data = _v25_project([{"id": "r1"}, {"id": "r2", "custom_metadata": {}}])
    migrated = _apply_migration_v25_to_v26(data)
    for rel in migrated["relations"]:
        assert rel["birth_year"] is None
        assert rel["death_year"] is None


def test_v25_to_v26_ignores_non_numeric_metadata():
    data = _v25_project([
        {"id": "r1", "custom_metadata": {"birth_year": "hace mucho", "death_year": None}},
    ])
    rel = _apply_migration_v25_to_v26(data)["relations"][0]
    assert rel["birth_year"] is None
    assert rel["death_year"] is None


def test_v25_to_v26_respects_existing_first_class_fields():
    data = _v25_project([
        {"id": "r1", "birth_year": 900, "custom_metadata": {"birth_year": "1200"}},
    ])
    rel = _apply_migration_v25_to_v26(data)["relations"][0]
    assert rel["birth_year"] == 900


def test_v25_to_v26_passes_through_non_dict_relations_and_missing_collection():
    data = _v25_project(["cadena rara"])
    assert _apply_migration_v25_to_v26(data)["relations"] == ["cadena rara"]
    no_relations = {"id": "p1", "schema_version": 25}
    assert _apply_migration_v25_to_v26(no_relations)["schema_version"] == 26
