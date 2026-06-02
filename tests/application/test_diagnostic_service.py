from __future__ import annotations

import json

from packages.application.diagnostic_service import (
    DiagnosticSeverity,
    DiagnosticService,
)
from packages.domain.candidate_issue import (
    Candidate,
    CandidateState,
    StructuredIssue,
    StructuredIssueSeverity,
)
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Ok
from packages.domain.source_history import HistoryEntry, Source


def test_diagnose_healthy_project_is_read_only_and_exports_counts() -> None:
    project = Project(name="Healthy")
    entity_a = NarrativeEntity(id="e-a", name="A")
    entity_b = NarrativeEntity(id="e-b", name="B")
    project.entities.extend([entity_a, entity_b])
    project.relations.append(NarrativeRelation(id="r-ok", source_id="e-a", target_id="e-b"))
    before = project.to_dict()

    result = DiagnosticService().diagnose(project)

    assert isinstance(result, Ok)
    report = result.value
    assert report.project_id == project.id
    assert report.counts["entities"] == 2
    assert report.counts["relations"] == 1
    assert report.size["serialized_json_bytes"] > 0
    assert report.error_count == 0
    assert project.to_dict() == before

    exported = json.loads(report.to_json())
    assert exported["counts"]["entities"] == 2
    assert exported["error_count"] == 0
    assert "## Diagnóstico de integridad" in report.to_markdown()


def test_diagnose_detects_broken_references_and_obsolete_data() -> None:
    project = Project(name="Corrupt controlled")
    project.entities.append(NarrativeEntity(id="e-live", name="Live"))
    project.entities.append(NarrativeEntity(id="e-old", name="Old", canon_state=CanonState.OBSOLETO))
    project.relations.append(NarrativeRelation(id="r-broken", source_id="e-live", target_id="missing-entity"))
    project.issues.append(
        StructuredIssue(
            id="i-broken",
            severity=StructuredIssueSeverity.ALTA,
            description="Broken issue",
            affected_entity_ids=["missing-entity"],
        )
    )

    report = DiagnosticService().diagnose(project).value

    codes = {item.code for item in report.items}
    assert "broken_relation_target" in codes
    assert "broken_issue_entity" in codes
    assert "obsolete_entity" in codes
    assert report.error_count >= 2
    assert any(item.severity == DiagnosticSeverity.WARNING for item in report.items)


def test_diagnose_recommends_cleanup_for_accumulated_project_data() -> None:
    project = Project(name="Large queues")
    project.history = [HistoryEntry(id=f"h-{idx}", reason="event") for idx in range(101)]
    project.candidates = [Candidate(id=f"c-{idx}", state=CandidateState.PENDIENTE) for idx in range(21)]
    project.issues = [StructuredIssue(id=f"i-{idx}", description="open") for idx in range(21)]
    project.sources = [Source(id=f"s-{idx}", name="source") for idx in range(16)]

    report = DiagnosticService().diagnose(project).value

    recommendation_codes = {item.code for item in report.recommendations}
    assert "cleanup_history" in recommendation_codes
    assert "review_pending_candidates" in recommendation_codes
    assert "review_open_issues" in recommendation_codes
    assert "cleanup_sources" in recommendation_codes
    assert all(item.mutates_project is False for item in report.recommendations)
