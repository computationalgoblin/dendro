"""Migración v32 → v33 (BETA2-FOCO-01): jardín narrativo — riego de entidades.

Cambio puramente aditivo: colecciones ``watering_diagnostics`` y
``watering_paused_entity_ids`` a nivel de proyecto, vacías al migrar. El canon
(entidades, relaciones, cronología, metadata) queda intacto.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v32_to_v33,
    validate_schema_version,
)


def _v32_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "schema_version": 32,
        "entities": [{"id": "e1", "name": "Eldrin", "canon_state": "canonico"}],
        "relations": [{"id": "r1", "source_id": "e1", "target_id": "e2"}],
        "project_chronology": {"present_year": 1000, "eras": []},
        "metadata": {"clave": "valor"},
    }


@pytest.mark.persistence
def test_v33_is_supported():
    assert CURRENT_SCHEMA_VERSION >= 33
    assert MAX_SUPPORTED_VERSION >= 33


@pytest.mark.persistence
def test_migration_v32_to_v33_adds_empty_watering_collections():
    migrated = _apply_migration_v32_to_v33(_v32_project())

    assert migrated["schema_version"] == 33
    assert migrated["watering_diagnostics"] == []
    assert migrated["watering_paused_entity_ids"] == []


@pytest.mark.persistence
def test_migration_v32_to_v33_preserves_canon():
    migrated = _apply_migration_v32_to_v33(_v32_project())

    assert migrated["entities"][0]["name"] == "Eldrin"
    assert migrated["entities"][0]["canon_state"] == "canonico"
    assert migrated["relations"][0]["id"] == "r1"
    assert migrated["project_chronology"]["present_year"] == 1000
    assert migrated["metadata"] == {"clave": "valor"}


@pytest.mark.persistence
def test_migration_v32_to_v33_does_not_mutate_input():
    data = _v32_project()
    _apply_migration_v32_to_v33(data)

    assert data["schema_version"] == 32
    assert "watering_diagnostics" not in data
    assert "watering_paused_entity_ids" not in data


@pytest.mark.persistence
def test_migration_v32_to_v33_respects_existing_collections():
    # setdefault: si el dict ya trae datos de riego (guardado parcial), se conservan.
    data = _v32_project()
    data["watering_diagnostics"] = [{"id": "d1", "entity_id": "e1"}]
    data["watering_paused_entity_ids"] = ["e1"]

    migrated = _apply_migration_v32_to_v33(data)

    assert migrated["watering_diagnostics"] == [{"id": "d1", "entity_id": "e1"}]
    assert migrated["watering_paused_entity_ids"] == ["e1"]


@pytest.mark.persistence
def test_future_version_rejected():
    assert validate_schema_version(CURRENT_SCHEMA_VERSION) is None
    future = MAX_SUPPORTED_VERSION + 1
    error = validate_schema_version(future)
    assert error is not None
    assert f"v{future}" in error
