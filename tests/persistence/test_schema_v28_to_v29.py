"""Migración v28 → v29: modos de importación + taxonomía de proyecto.

Aditiva y sin pérdida: inicializa ``import_taxonomy`` y marca los baskets
previos como modo ``canon`` (comportamiento histórico). Verifica idempotencia,
no-pérdida de canon, bump de versión y validación estructural.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v28_to_v29,
)


def _v28_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 28,
        "entities": [{"id": "e1", "name": "Eldrin"}],
        "import_baskets": [
            {"id": "b1", "source_id": "s1", "metadata": {"file_path": "/tmp/x.md"}},
        ],
    }


@pytest.mark.persistence
def test_v29_is_supported():
    # v29 dejó de ser la última versión (ver test_schema_v30_chunking_version);
    # la cadena de migración debe seguir alcanzándola y superándola.
    assert CURRENT_SCHEMA_VERSION >= 29
    assert MAX_SUPPORTED_VERSION >= 29


@pytest.mark.persistence
def test_migration_v28_to_v29_initializes_taxonomy():
    migrated = _apply_migration_v28_to_v29(_v28_project())

    assert migrated["schema_version"] == 29
    tax = migrated["import_taxonomy"]
    assert tax == {
        "allowed_entity_types": [],
        "allowed_branch_types": [],
        "allowed_ring_ids": [],
        "extraction_guidance": "",
        "strict": False,
    }
    # No-pérdida del canon previo.
    assert migrated["entities"][0]["name"] == "Eldrin"


@pytest.mark.persistence
def test_migration_v28_to_v29_marks_old_baskets_as_canon():
    migrated = _apply_migration_v28_to_v29(_v28_project())

    basket = migrated["import_baskets"][0]
    assert basket["import_mode"] == "canon"
    assert basket["metadata"]["import_mode"] == "canon"
    # No pisa metadatos previos.
    assert basket["metadata"]["file_path"] == "/tmp/x.md"


@pytest.mark.persistence
def test_migration_v28_to_v29_preserves_existing_taxonomy():
    data = _v28_project()
    data["import_taxonomy"] = {
        "allowed_entity_types": ["personaje"],
        "allowed_branch_types": ["faccion"],
        "allowed_ring_ids": ["layer_narrativa"],
        "extraction_guidance": "solo el núcleo",
        "strict": True,
    }

    migrated = _apply_migration_v28_to_v29(data)

    assert migrated["import_taxonomy"]["allowed_entity_types"] == ["personaje"]
    assert migrated["import_taxonomy"]["strict"] is True


@pytest.mark.persistence
def test_migration_v28_to_v29_preserves_existing_basket_mode():
    data = _v28_project()
    data["import_baskets"][0]["import_mode"] = "contexto"

    migrated = _apply_migration_v28_to_v29(data)

    assert migrated["import_baskets"][0]["import_mode"] == "contexto"


@pytest.mark.persistence
def test_migration_v28_to_v29_is_idempotent():
    once = _apply_migration_v28_to_v29(_v28_project())
    twice = _apply_migration_v28_to_v29(once)
    assert twice == once


# PA04: la validación de import_taxonomy se eliminó de validate_project_structure
# (la taxonomía de importación ya no existe como sección de config). El test
# test_validate_rejects_non_dict_taxonomy se retiró por probar funcionalidad
# eliminada. Los modos de importación canon/contexto siguen vivos (arriba).
