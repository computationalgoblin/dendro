"""Migración v31 → v32 (I25): rediseño de importación map→reduce.

Rompe compatibilidad de los candidatos de importación viejos (proyecto en beta):
vacía ``import_candidates``, resetea el progreso de extracción IA y deja ``graph``
en None, pero CONSERVA los ``segments``, el vínculo a la ``Source`` y todo el canon.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v31_to_v32,
)


def _v31_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "schema_version": 31,
        "entities": [{"id": "e1", "name": "Eldrin"}],
        "relations": [{"id": "r1", "source_id": "e1", "target_id": "e2"}],
        "project_chronology": {"present_year": 1000, "eras": []},
        "import_baskets": [
            {
                "id": "b1",
                "source_id": "s1",
                "segments": [{"id": "seg1", "raw_text": "texto del documento"}],
                "import_candidates": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}],
                "review_state": "parcial",
                "metadata": {
                    "file_name": "doc.md",
                    "ai_extraction": {"completed_window_keys": ["w0"], "total_windows": 3},
                    "ai_grouping": {"error": "x"},
                },
            },
        ],
    }


@pytest.mark.persistence
def test_v32_is_supported():
    assert CURRENT_SCHEMA_VERSION >= 32
    assert MAX_SUPPORTED_VERSION >= 32


@pytest.mark.persistence
def test_migration_v31_to_v32_discards_old_candidates_keeps_segments():
    migrated = _apply_migration_v31_to_v32(_v31_project())

    assert migrated["schema_version"] == 32
    basket = migrated["import_baskets"][0]
    # Candidatos viejos descartados; grafo aún no calculado.
    assert basket["import_candidates"] == []
    assert basket["graph"] is None
    assert basket["review_state"] == "pendiente"
    # Segmentos y vínculo a la fuente conservados (re-extraer sin re-subir).
    assert len(basket["segments"]) == 1
    assert basket["source_id"] == "s1"


@pytest.mark.persistence
def test_migration_v31_to_v32_resets_extraction_progress_keeps_useful_meta():
    migrated = _apply_migration_v31_to_v32(_v31_project())

    meta = migrated["import_baskets"][0]["metadata"]
    assert "ai_extraction" not in meta
    assert "ai_grouping" not in meta
    assert meta["schema_v32_reset"] is True
    # Metadata útil (nombre de fichero) intacta.
    assert meta["file_name"] == "doc.md"


@pytest.mark.persistence
def test_migration_v31_to_v32_preserves_canon():
    migrated = _apply_migration_v31_to_v32(_v31_project())

    assert migrated["entities"][0]["name"] == "Eldrin"
    assert migrated["relations"][0]["id"] == "r1"
    assert migrated["project_chronology"]["present_year"] == 1000


@pytest.mark.persistence
def test_migration_v31_to_v32_does_not_mutate_input():
    data = _v31_project()
    _apply_migration_v31_to_v32(data)
    # El original conserva sus candidatos (la migración trabaja sobre copia).
    assert len(data["import_baskets"][0]["import_candidates"]) == 3
    assert data["schema_version"] == 31


@pytest.mark.persistence
def test_migration_v31_to_v32_handles_no_baskets():
    data = {"id": "p", "schema_version": 31, "entities": []}
    migrated = _apply_migration_v31_to_v32(data)
    assert migrated["schema_version"] == 32
    assert "import_baskets" not in migrated
