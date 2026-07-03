"""Migración v33 → v34 (BETA2-FOCO-16): canon total.

Decisión de producto: algo es canon salvo que haya sido declarado fantasma.
Las entidades y relaciones en ``borrador`` pasan a ``canonico``; el resto de
estados (fantasma, archivado, hipotesis, ...) queda intacto. Sin pérdida.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v33_to_v34,
    validate_schema_version,
)


def _v33_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "schema_version": 33,
        "entities": [
            {"id": "e1", "name": "Eldrin", "canon_state": "borrador"},
            {"id": "e2", "name": "Umbra", "canon_state": "fantasma"},
            {"id": "e3", "name": "Aria", "canon_state": "canonico"},
            {"id": "e4", "name": "Viejo", "canon_state": "archivado"},
        ],
        "relations": [
            {"id": "r1", "source_id": "e1", "target_id": "e3", "canon_state": "borrador"},
            {"id": "r2", "source_id": "e2", "target_id": "e3", "canon_state": "fantasma"},
        ],
        "watering_diagnostics": [{"id": "d1", "entity_id": "e1"}],
        "watering_paused_entity_ids": ["e3"],
        "metadata": {"last_worked_entity_id": "e1"},
    }


@pytest.mark.persistence
def test_v34_is_supported():
    assert CURRENT_SCHEMA_VERSION >= 34
    assert MAX_SUPPORTED_VERSION >= 34


@pytest.mark.persistence
def test_migration_v33_to_v34_promotes_borrador_to_canonico():
    migrated = _apply_migration_v33_to_v34(_v33_project())

    assert migrated["schema_version"] == 34
    assert migrated["entities"][0]["canon_state"] == "canonico"
    assert migrated["relations"][0]["canon_state"] == "canonico"


@pytest.mark.persistence
def test_migration_v33_to_v34_preserves_other_states():
    migrated = _apply_migration_v33_to_v34(_v33_project())

    assert migrated["entities"][1]["canon_state"] == "fantasma"
    assert migrated["entities"][2]["canon_state"] == "canonico"
    assert migrated["entities"][3]["canon_state"] == "archivado"
    assert migrated["relations"][1]["canon_state"] == "fantasma"


@pytest.mark.persistence
def test_migration_v33_to_v34_preserves_watering_and_metadata():
    migrated = _apply_migration_v33_to_v34(_v33_project())

    assert migrated["watering_diagnostics"] == [{"id": "d1", "entity_id": "e1"}]
    assert migrated["watering_paused_entity_ids"] == ["e3"]
    assert migrated["metadata"] == {"last_worked_entity_id": "e1"}


@pytest.mark.persistence
def test_migration_v33_to_v34_does_not_mutate_input():
    data = _v33_project()
    _apply_migration_v33_to_v34(data)

    assert data["schema_version"] == 33
    assert data["entities"][0]["canon_state"] == "borrador"
    assert data["relations"][0]["canon_state"] == "borrador"


@pytest.mark.persistence
def test_migration_v33_to_v34_tolerates_missing_collections():
    # Un dict mínimo (sin entities/relations o con tipos raros) no debe romper.
    migrated = _apply_migration_v33_to_v34({"id": "p1", "schema_version": 33})
    assert migrated["schema_version"] == 34

    weird = _apply_migration_v33_to_v34(
        {"id": "p1", "schema_version": 33, "entities": "no-una-lista", "relations": None}
    )
    assert weird["schema_version"] == 34
    assert weird["entities"] == "no-una-lista"


@pytest.mark.persistence
def test_future_version_rejected():
    assert validate_schema_version(CURRENT_SCHEMA_VERSION) is None
    future = MAX_SUPPORTED_VERSION + 1
    error = validate_schema_version(future)
    assert error is not None
    assert f"v{future}" in error
