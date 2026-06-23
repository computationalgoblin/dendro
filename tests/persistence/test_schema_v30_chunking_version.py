"""Migración v29 → v30: versionado del troceado de documentos (I11).

Aditiva y sin pérdida: sella ``chunking_version: 1`` en los segmentos ya
persistidos (troceado histórico por párrafo) sin re-trocear ni tocar canon.
Verifica el bump de versión, la no-pérdida, el respeto de versiones previas y
la idempotencia.
"""

from __future__ import annotations

import pytest

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v29_to_v30,
)


def _v29_project():
    return {
        "id": "p1",
        "name": "Proyecto",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 29,
        "entities": [{"id": "e1", "name": "Eldrin"}],
        "import_baskets": [
            {
                "id": "b1",
                "source_id": "s1",
                "metadata": {"file_path": "/tmp/x.md"},
                "segments": [
                    {"id": "s1-chunk-0001", "raw_text": "Texto",
                     "metadata": {"chunk_id": "s1-chunk-0001"}},
                    {"id": "s1-chunk-0002", "raw_text": "Más",
                     "metadata": {"chunk_id": "s1-chunk-0002"}},
                ],
            },
        ],
    }


@pytest.mark.persistence
def test_current_version_is_30():
    assert CURRENT_SCHEMA_VERSION == 30
    assert MAX_SUPPORTED_VERSION == 30


@pytest.mark.persistence
def test_migration_v29_to_v30_stamps_legacy_chunking_version():
    migrated = _apply_migration_v29_to_v30(_v29_project())

    assert migrated["schema_version"] == 30
    segments = migrated["import_baskets"][0]["segments"]
    assert all(seg["metadata"]["chunking_version"] == 1 for seg in segments)
    # No-pérdida: ids, texto y canon intactos.
    assert segments[0]["metadata"]["chunk_id"] == "s1-chunk-0001"
    assert segments[1]["raw_text"] == "Más"
    assert migrated["entities"][0]["name"] == "Eldrin"


@pytest.mark.persistence
def test_migration_v29_to_v30_preserves_existing_chunking_version():
    data = _v29_project()
    data["import_baskets"][0]["segments"][0]["metadata"]["chunking_version"] = 2

    migrated = _apply_migration_v29_to_v30(data)

    segs = migrated["import_baskets"][0]["segments"]
    assert segs[0]["metadata"]["chunking_version"] == 2  # no pisa el nuevo troceado
    assert segs[1]["metadata"]["chunking_version"] == 1


@pytest.mark.persistence
def test_migration_v29_to_v30_handles_baskets_without_segments():
    data = _v29_project()
    data["import_baskets"][0].pop("segments")

    migrated = _apply_migration_v29_to_v30(data)

    assert migrated["schema_version"] == 30  # no revienta sin segmentos


@pytest.mark.persistence
def test_migration_v29_to_v30_is_idempotent():
    once = _apply_migration_v29_to_v30(_v29_project())
    twice = _apply_migration_v29_to_v30(once)
    assert twice == once
