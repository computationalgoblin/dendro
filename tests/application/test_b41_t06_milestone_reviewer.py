"""Tests for B41-T06: Causal milestone candidate reviewer."""

import pytest

from packages.application.causal_milestone_reviewer import (
    ReviewFinding,
    ReviewSeverity,
    review_causal_milestone,
)
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.candidate_service import CandidateService
from packages.application.project_service import ProjectService
from packages.domain.entity import NarrativeEntity, EntityType
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="B41-T06")
    cs = CandidateService(ps)
    ms = CausalMilestoneService(ps, candidate_service=cs)
    return ps, ms


@pytest.mark.application
def test_review_detects_orphan_milestone_no_context():
    """A milestone with no affected entities/relations should flag as weak."""
    ps, ms = _setup()
    hito = ms.create_hito_manual({
        "title": "Evento aislado",
        "description": "Un hito sin conexiones.",
    }).value

    findings = review_causal_milestone(hito, ps.active_project)
    severities = [f.severity for f in findings]
    assert ReviewSeverity.WARNING in severities or ReviewSeverity.INFO in severities


@pytest.mark.application
def test_review_passes_well_connected_milestone():
    ps, ms = _setup()
    ps.active_project.entities.append(NarrativeEntity(
        id="e1", name="Cultura X", entity_type=EntityType.FACCION,
    ))
    ps.active_project.relations.append(NarrativeRelation(
        id="r1", source_id="e1", target_id="e2", relation_type=RelationType.CAUSO,
    ))
    hito = ms.create_hito_manual({
        "title": "Guerra de los Dos Soles",
        "description": "Conflicto fundacional.",
        "affected_entity_ids": ["e1"],
        "caused_relation_ids": ["r1"],
        "causal_parent_hito_ids": [],
    }).value

    findings = review_causal_milestone(hito, ps.active_project)
    criticals = [f for f in findings if f.severity == ReviewSeverity.CRITICAL]
    assert len(criticals) == 0


@pytest.mark.application
def test_review_detects_contradiction_with_parent():
    ps, ms = _setup()
    parent = ms.create_hito_manual({
        "id": "h_parent",
        "title": "Paz eterna",
        "description": "Nunca hubo guerra.",
    }).value
    hito = ms.create_hito_manual({
        "title": "Guerra fundacional",
        "description": "La primera gran guerra.",
        "causal_parent_hito_ids": ["h_parent"],
    }).value

    findings = review_causal_milestone(hito, ps.active_project)
    labels = [f.label for f in findings]
    assert any("contradic" in l.lower() or "tensión" in l.lower() for l in labels)


@pytest.mark.application
def test_review_finding_serializes():
    f = ReviewFinding(
        label="Redundancia detectada",
        severity=ReviewSeverity.WARNING,
        detail="El hito repite lo que ya explica H-001.",
    )
    d = f.to_dict()
    assert d["severity"] == "warning"
    restored = ReviewFinding.from_dict(d)
    assert restored.label == f.label
