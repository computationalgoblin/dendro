"""BETA2-WIKI-02: migración v38→v39 y persistencia de la página de wiki.

La Memoria (``NarrativeMemory``) gana ``cuerpo``/``wikilinks``/``tags`` para servir
de página de wiki. La migración es aditiva y sin pérdida; los campos nuevos son
tolerantes al cargar proyectos v38.
"""

import json

import pytest

from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v38_to_v39,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_is_v39():
    assert CURRENT_SCHEMA_VERSION >= 39


@pytest.mark.persistence
def test_migration_v38_to_v39_is_additive_without_loss():
    data = {"schema_version": 38, "name": "L", "entities": [{"id": "e1"}]}
    migrated = _apply_migration_v38_to_v39(data)
    assert migrated["schema_version"] == 39
    assert migrated["narrative_memories"] == []
    assert migrated["entities"] == [{"id": "e1"}]


@pytest.mark.persistence
def test_migration_v38_to_v39_preserves_existing_pages():
    page = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY, target_id="e1", resumen_editorial="lead"
    ).to_dict()
    data = {"schema_version": 38, "narrative_memories": [page]}
    migrated = _apply_migration_v38_to_v39(data)
    assert migrated["narrative_memories"] == [page]


@pytest.mark.persistence
def test_load_project_data_migrates_v38_to_v39(tmp_path):
    old = Project(id="p38", name="Legacy v38").to_dict()
    old["schema_version"] = 38
    old.pop("narrative_memories", None)
    path = tmp_path / "legacy-v38.json"
    path.write_text(json.dumps(old, default=str), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["narrative_memories"] == []


@pytest.mark.persistence
def test_page_body_links_tags_roundtrip(tmp_path):
    project = Project(id="pw", name="Wiki")
    project.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            resumen_editorial="Ana, reina en el exilio.",
            cuerpo="Ana perdió el trono tras la traición de Beto. Ahora conspira desde el sur.",
            wikilinks=[
                MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="e2", nota="Beto"),
            ],
            tags=["realeza", "exilio"],
        )
    )
    path = tmp_path / "wiki.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    pages = loaded.value.narrative_memories
    assert len(pages) == 1
    page = pages[0]
    assert page.cuerpo.startswith("Ana perdió el trono")
    assert page.tags == ["realeza", "exilio"]
    assert len(page.wikilinks) == 1
    assert page.wikilinks[0].ref_id == "e2"
    assert page.wikilinks[0].ref_kind == MemoryTargetKind.ENTITY


@pytest.mark.persistence
def test_old_page_without_new_fields_loads_with_defaults():
    # Un bloque v38 sin los campos nuevos carga con defaults vacíos (tolerante).
    legacy = {
        "target_kind": "entity",
        "target_id": "e1",
        "resumen_editorial": "solo lead",
    }
    page = NarrativeMemory.from_dict(legacy)
    assert page.cuerpo == ""
    assert page.wikilinks == []
    assert page.tags == []


@pytest.mark.persistence
def test_content_snapshot_includes_body_for_diff():
    page = NarrativeMemory(cuerpo="cuerpo largo", tags=["t"])
    snap = page.content_snapshot()
    assert snap["cuerpo"] == "cuerpo largo"
    assert snap["tags"] == ["t"]
