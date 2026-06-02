from __future__ import annotations

import copy
import json

from packages.application.diagnostic_service import DiagnosticService
from packages.application.repair_plan_service import RepairPlanService
from packages.domain.entity import CanonState, EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok


def _broken_project() -> Project:
    project = Project(id="p1", name="Repair Plan")
    project.entities.append(
        NarrativeEntity(
            id="e1",
            name="Old NPC",
            entity_type=EntityType.PERSONAJE,
            canon_state=CanonState.OBSOLETO,
        )
    )
    project.relations.append(
        NarrativeRelation(
            id="r1",
            source_id="e1",
            target_id="missing-target",
            relation_type=RelationType.ESTA_RELACIONADO_CON,
        )
    )
    return project


def test_repair_plan_service_generates_non_destructive_actions() -> None:
    project = _broken_project()
    before = copy.deepcopy(project.to_dict())

    result = RepairPlanService(diagnostic_service=DiagnosticService()).build_plan(project)

    assert isinstance(result, Ok)
    plan = result.value
    assert plan.mutates_project is False
    assert plan.requires_explicit_apply is True
    assert plan.requires_backup_before_apply is True
    assert project.to_dict() == before
    codes = {action.diagnostic_code for action in plan.actions}
    assert "broken_relation_target" in codes
    assert "obsolete_entity" in codes
    for action in plan.actions:
        assert action.impact
        assert action.preflight
        assert action.requires_backup_before_apply is True
        assert action.mutates_project is False


def test_repair_plan_json_and_markdown_are_verifiable() -> None:
    plan = RepairPlanService().build_plan(_broken_project()).value

    data = json.loads(plan.to_json())
    assert data["project_id"] == "p1"
    assert data["mutates_project"] is False
    assert data["requires_backup_before_apply"] is True
    assert data["actions"]
    assert {"id", "diagnostic_code", "severity", "impact", "preflight"}.issubset(data["actions"][0])

    markdown = plan.to_markdown()
    assert "# Repair plan" in markdown
    assert "No automatic mutation" in markdown
    assert "broken_relation_target" in markdown


def test_repair_plan_from_existing_report_does_not_duplicate_diagnostics() -> None:
    service = RepairPlanService()
    report = DiagnosticService().diagnose(_broken_project()).value

    plan = service.build_plan_from_report(report).value

    assert len(plan.actions) == len(report.items) + len(report.recommendations)
    assert all(action.source == "diagnostic" for action in plan.actions)
