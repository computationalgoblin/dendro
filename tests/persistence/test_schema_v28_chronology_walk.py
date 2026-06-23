"""CRON — Migración v27 → v28: recorrido cronológico persistente.

Aditiva: inicializa las colecciones del Modo Creación Cronológica sin tocar
canon. Verifica idempotencia, no-pérdida de datos previos y bump de versión.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v27_to_v28,
    validate_project_structure,
)


def _v27_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 27,
        "causal_milestones": [{"id": "h1", "title": "Origen", "year": 0}],
    }


@pytest.mark.persistence
def test_schema_supports_at_least_v28():
    # v28 dejó de ser la última versión (ver test_schema_v28_to_v29); la cadena
    # de migraciones debe seguir soportando proyectos hasta v28 como mínimo.
    assert CURRENT_SCHEMA_VERSION >= 28
    assert MAX_SUPPORTED_VERSION >= 28


@pytest.mark.persistence
def test_migration_v27_to_v28_adds_empty_walk_collections():
    migrated = _apply_migration_v27_to_v28(_v27_project())

    assert migrated["schema_version"] == 28
    assert migrated["chronology_walk_sessions"] == []
    assert migrated["chronology_walk_reports"] == []
    # No-pérdida del canon previo.
    assert migrated["causal_milestones"][0]["title"] == "Origen"


@pytest.mark.persistence
def test_migration_v27_to_v28_preserves_existing_collections():
    data = _v27_project()
    data["chronology_walk_sessions"] = [{"id": "walk_x"}]
    data["chronology_walk_reports"] = [{"id": "walkrep_y"}]

    migrated = _apply_migration_v27_to_v28(data)

    assert migrated["chronology_walk_sessions"] == [{"id": "walk_x"}]
    assert migrated["chronology_walk_reports"] == [{"id": "walkrep_y"}]


@pytest.mark.persistence
def test_migration_v27_to_v28_is_idempotent():
    once = _apply_migration_v27_to_v28(_v27_project())
    twice = _apply_migration_v27_to_v28(once)
    assert twice == once


@pytest.mark.persistence
def test_validate_rejects_non_list_walk_sessions():
    data = _v27_project()
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    data["chronology_walk_sessions"] = {"not": "a list"}

    error = validate_project_structure(data)

    assert error == "Project collection 'chronology_walk_sessions' must be a JSON array, got dict"
