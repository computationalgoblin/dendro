"""CRON — Round-trip de sesiones e informes de recorrido cronológico.

Project → ProjectStore.save → load sin pérdida. También un proyecto v27 viejo
cargado por el store gana las colecciones vacías (migración encadenada).
"""

from __future__ import annotations

import json

import pytest

from packages.domain.chronology_walk import (
    ChronologyWalkReport,
    ChronologyWalkSession,
    WalkAggressiveness,
    WalkDepth,
    WalkDirection,
    WalkMode,
    WalkStatus,
)
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore


@pytest.mark.persistence
def test_project_store_roundtrips_walk_sessions_and_reports(tmp_path):
    project = Project(id="proj-cron", name="CRON")
    project.chronology_walk_sessions.append(
        ChronologyWalkSession(
            id="walk_1",
            direction=WalkDirection.PAST,
            mode=WalkMode.CONSISTENCIA,
            depth=WalkDepth.PROFUNDA,
            aggressiveness=WalkAggressiveness.NUEVAS_PIEZAS,
            start_milestone_id="hito-3",
            current_milestone_id="hito-2",
            visited_milestone_ids=["hito-3", "hito-2"],
            accumulated_summary="La caída del gremio está bien motivada.",
            open_problems=[
                {"id": "p1", "kind": "causal_gap", "severity": "alta", "resolved": False}
            ],
            decisions=[{"milestone_id": "hito-2", "decision": "pospuesto"}],
            generated_candidate_ids=["cand-1"],
            status=WalkStatus.PAUSED,
        )
    )
    project.chronology_walk_reports.append(
        ChronologyWalkReport(
            id="walkrep_1",
            session_id="walk_1",
            verdict="Parcialmente coherente",
            milestones_analyzed=["hito-3", "hito-2"],
            timeline_reviewed_up_to_milestone_id="hito-2",
            recommended_next_steps=["Crear hito de la Purga."],
        )
    )
    path = tmp_path / "cron.json"

    store = ProjectStore()
    save_result = store.save(project, path)
    load_result = store.load(path)

    assert isinstance(save_result, Ok)
    assert isinstance(load_result, Ok)
    loaded = load_result.value
    assert loaded.chronology_walk_sessions == project.chronology_walk_sessions
    assert loaded.chronology_walk_reports == project.chronology_walk_reports


@pytest.mark.persistence
def test_store_migrates_v27_project_file_gaining_empty_walk_collections(tmp_path):
    data = Project(id="proj-old", name="Legacy v27").to_dict()
    data["schema_version"] = 27
    data.pop("chronology_walk_sessions", None)
    data.pop("chronology_walk_reports", None)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    load_result = ProjectStore().load(path)

    assert isinstance(load_result, Ok)
    assert load_result.value.chronology_walk_sessions == []
    assert load_result.value.chronology_walk_reports == []
