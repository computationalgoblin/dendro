"""Tests for B41-T07: Status quo explained by milestones."""

import pytest

from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.candidate_service import CandidateService
from packages.application.project_service import ProjectService
from packages.application.status_quo_explainer import explain_status_quo
from packages.domain.entity import NarrativeEntity, EntityType
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="B41-T07")
    cs = CandidateService(ps)
    ms = CausalMilestoneService(ps, candidate_service=cs)
    return ps, ms


@pytest.mark.application
def test_empty_project_status_quo():
    ps, _ = _setup()
    report = explain_status_quo(ps.active_project)
    assert report["summary"] != ""
    assert report["hitos_count"] == 0


@pytest.mark.application
def test_status_quo_counts_orphans_and_gaps():
    ps, ms = _setup()
    ms.create_hito_manual({
        "title": "Guerra de los Soles",
        "description": "Conflicto original.",
        "affected_entity_ids": ["e1"],
        "caused_relation_ids": ["r1"],
    })
    ps.active_project.relations.append(NarrativeRelation(
        id="r_orphan", source_id="a", target_id="b",
        relation_type=RelationType.CAUSO,
    ))
    report = explain_status_quo(ps.active_project)
    assert report["hitos_count"] == 1
    assert report["relations_without_hito"] >= 1
    assert "hitos_without_consequences" in report
    assert isinstance(report.get("opportunities", []), list)


@pytest.mark.application
def test_status_quo_report_serializable():
    ps, ms = _setup()
    ms.create_hito_manual({"title": "H1", "affected_entity_ids": ["e1"]})
    report = explain_status_quo(ps.active_project)
    import json
    serialized = json.dumps(report)
    assert "hitos_count" in serialized
