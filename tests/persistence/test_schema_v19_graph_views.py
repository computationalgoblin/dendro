from __future__ import annotations

import json
from datetime import datetime, timezone

from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.schema import CURRENT_SCHEMA_VERSION, MAX_SUPPORTED_VERSION
from packages.persistence.store import load_project_data, save_project_data


def _base_v18() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 18,
        "id": "proj_v18",
        "name": "V18",
        "created_at": now,
        "updated_at": now,
        "general": {},
        "tone": {},
        "genre": {},
        "realism": {},
        "ai": {},
        "visibility": {},
        "export": {},
        "project_metadata": {},
        "advanced_config": {},
        "entities": [],
        "relations": [],
        "sources": [],
        "history": [],
        "issues": [],
        "structured_issues": [],
        "narrative_frameworks": [],
        "framework_templates": [],
        "timeline_events": [],
        "writing_units": [],
        "custom_entity_types": [],
        "custom_field_definitions": [],
        "custom_relation_types": [],
        "domains": ["mundo"],
        "world_layers": [],
        "import_baskets": [],
        "campaigns": [],
        "player_character_profiles": [],
        "campaign_clocks": [],
        "secrets": [],
        "clues": [],
        "factions": [],
        "fronts": [],
        "sessions": [],
    }


def test_schema_v19_constants() -> None:
    assert CURRENT_SCHEMA_VERSION >= 20
    assert MAX_SUPPORTED_VERSION == CURRENT_SCHEMA_VERSION


def test_v18_migration_adds_saved_graph_views_without_inventing_views(tmp_path) -> None:
    path = tmp_path / "project.json"
    path.write_text(json.dumps(_base_v18()), encoding="utf-8")

    result = load_project_data(path)

    assert isinstance(result, Ok)
    assert result.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert result.value["saved_graph_views"] == []


def test_saved_graph_views_must_be_json_array(tmp_path) -> None:
    data = _base_v18()
    data["schema_version"] = 19
    data["saved_graph_views"] = {"bad": "not-list"}
    path = tmp_path / "project.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    result = load_project_data(path)

    assert not isinstance(result, Ok)
    assert "saved_graph_views" in result.error
    assert "JSON array" in result.error


def test_project_roundtrip_preserves_saved_graph_view_config(tmp_path) -> None:
    project = Project(name="Graph views")
    project.saved_graph_views.append(
        {
            "id": "gv_1",
            "name": "Player secrets",
            "filters": {"view_type": "secretos", "audience": "player"},
            "layout_preferences": {"algorithm": "circular", "positions": {"n1": [1, 2]}},
        },
    )
    path = tmp_path / "project.json"

    save_result = save_project_data(project.to_dict(), path)
    assert isinstance(save_result, Ok)
    load_result = load_project_data(path)

    assert isinstance(load_result, Ok)
    loaded = Project.from_dict(load_result.value)
    assert loaded.saved_graph_views == project.saved_graph_views
