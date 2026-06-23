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


@pytest.mark.domain
def test_session_defaults():
    session = ChronologyWalkSession()
    assert session.id.startswith("walk_")
    assert session.direction is WalkDirection.FUTURE
    assert session.mode is WalkMode.MIXTO
    assert session.depth is WalkDepth.NORMAL
    assert session.aggressiveness is WalkAggressiveness.REPARAR
    assert session.status is WalkStatus.ACTIVE
    assert session.report_id is None
    assert session.created_at and session.updated_at


@pytest.mark.domain
def test_session_roundtrip_preserves_all_fields():
    session = ChronologyWalkSession(
        id="walk_test",
        direction=WalkDirection.PAST,
        mode=WalkMode.CONSISTENCIA,
        depth=WalkDepth.PROFUNDA,
        aggressiveness=WalkAggressiveness.NUEVAS_PIEZAS,
        start_milestone_id="hito-3",
        current_milestone_id="hito-2",
        visited_milestone_ids=["hito-3", "hito-2"],
        accumulated_summary="La caída del gremio está bien motivada.",
        open_problems=[
            {
                "id": "p1",
                "milestone_id": "hito-2",
                "kind": "motivation_incompatibility",
                "severity": "alta",
                "title": "Servidumbre no motivada",
                "description": "Falta justificar la obediencia.",
                "resolved": False,
            }
        ],
        decisions=[{"milestone_id": "hito-2", "decision": "pospuesto", "note": "", "at": "x"}],
        generated_candidate_ids=["cand-1", "cand-2"],
        last_narrative_state={"tension": "deuda vs persecución"},
        status=WalkStatus.PAUSED,
        report_id="walkrep_x",
        created_at="2026-06-22T10:00:00+00:00",
        updated_at="2026-06-22T10:30:00+00:00",
        metadata={"origin": "test"},
    )

    restored = ChronologyWalkSession.from_dict(session.to_dict())

    assert restored == session


@pytest.mark.domain
def test_session_from_dict_unknown_enum_falls_back_to_default():
    restored = ChronologyWalkSession.from_dict(
        {
            "id": "walk_x",
            "direction": "sideways",
            "mode": "???",
            "depth": "bogus",
            "aggressiveness": "nope",
            "status": "weird",
        }
    )
    assert restored.direction is WalkDirection.FUTURE
    assert restored.mode is WalkMode.MIXTO
    assert restored.depth is WalkDepth.NORMAL
    assert restored.aggressiveness is WalkAggressiveness.REPARAR
    assert restored.status is WalkStatus.ACTIVE


@pytest.mark.domain
def test_session_from_dict_drops_non_dict_problems():
    restored = ChronologyWalkSession.from_dict(
        {"open_problems": [{"id": "p1"}, "garbage", 42], "decisions": ["x", {"decision": "ok"}]}
    )
    assert restored.open_problems == [{"id": "p1"}]
    assert restored.decisions == [{"decision": "ok"}]


@pytest.mark.domain
def test_report_roundtrip_preserves_all_fields():
    report = ChronologyWalkReport(
        id="walkrep_test",
        session_id="walk_test",
        direction=WalkDirection.FUTURE,
        mode=WalkMode.MIXTO,
        range_start_milestone_id="hito-1",
        range_end_milestone_id="hito-8",
        milestones_analyzed=["hito-1", "hito-2", "hito-8"],
        verdict="Parcialmente coherente",
        critical_gaps=[{"milestone_id": "hito-2", "kind": "causal_gap", "title": "Falta causa"}],
        contradictions=[
            {"milestone_id": "hito-5", "kind": "contradiction", "title": "Orden imposible"}
        ],
        candidates_created=["cand-1"],
        decisions=[{"milestone_id": "hito-2", "decision": "crear_hito"}],
        timeline_reviewed_up_to_milestone_id="hito-8",
        recommended_next_steps=["Crear hito previo de la Purga."],
        created_at="2026-06-22T11:00:00+00:00",
        metadata={"mode_used": "mixto"},
    )

    restored = ChronologyWalkReport.from_dict(report.to_dict())

    assert restored == report


@pytest.mark.domain
def test_report_defaults():
    report = ChronologyWalkReport()
    assert report.id.startswith("walkrep_")
    assert report.direction is WalkDirection.FUTURE
    assert report.created_at
