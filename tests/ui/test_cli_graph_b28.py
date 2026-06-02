from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]


def _base_project() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 19,
        "id": "cli_graph",
        "name": "CLI Graph",
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
        "entities": [
            {
                "id": "hero",
                "name": "Hero",
                "entity_type": "personaje",
                "canon_state": "canonico",
                "visibility_state": "visible_jugadores",
            },
            {
                "id": "secret",
                "name": "Secret",
                "entity_type": "secreto",
                "canon_state": "canonico",
                "visibility_state": "privado_autor",
            },
        ],
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
        "saved_graph_views": [],
    }


def _cli(project: Path, args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    return subprocess.run(
        [sys.executable, "-m", "narrative_architect", "--project", str(project), *shlex.split(args)],
        cwd=WORKSPACE,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_graph_export_specialized_json_respects_player_no_leak(tmp_path) -> None:
    project = tmp_path / "project.json"
    project.write_text(json.dumps(_base_project()), encoding="utf-8")

    result = _cli(project, "graph export --json --view-type secretos --audience player")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["view_type"] == "secretos"
    assert data["nodes"] == []
    assert "Secret" not in result.stdout


def test_graph_view_save_list_show_uses_schema_v19_saved_graph_views(tmp_path) -> None:
    project = tmp_path / "project.json"
    project.write_text(json.dumps(_base_project()), encoding="utf-8")

    save = _cli(project, "graph view save player-secrets --view-type secretos --audience player --overlay secrets")
    assert save.returncode == 0, save.stderr
    list_result = _cli(project, "graph view list --json")
    show_result = _cli(project, "graph view show player-secrets")

    listed = json.loads(list_result.stdout)
    shown = json.loads(show_result.stdout)
    raw = json.loads(project.read_text(encoding="utf-8"))
    assert listed["views"][0]["name"] == "player-secrets"
    assert shown["filters"]["view_type"] == "secretos"
    assert raw["saved_graph_views"][0]["name"] == "player-secrets"
    serialized_saved = json.dumps(raw["saved_graph_views"])
    assert '"nodes"' not in serialized_saved
    assert '"edges"' not in serialized_saved


def test_graph_compare_json_reports_added_removed_changed(tmp_path) -> None:
    project = tmp_path / "project.json"
    data = _base_project()
    data["saved_graph_views"] = [
        {"id": "a", "name": "characters", "filters": {"view_type": "personaje"}},
        {"id": "b", "name": "all", "filters": {"view_type": "global"}},
    ]
    project.write_text(json.dumps(data), encoding="utf-8")

    result = _cli(project, "graph compare --view-a characters --view-b all --json")

    assert result.returncode == 0, result.stderr
    comparison = json.loads(result.stdout)
    assert {n["id"] for n in comparison["added_nodes"]} == {"secret"}
    assert comparison["view_a_id"] == "characters"
    assert comparison["view_b_id"] == "all"
