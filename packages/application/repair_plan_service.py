"""Non-destructive repair plan generation for B29."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from packages.application.diagnostic_service import DiagnosticItem, DiagnosticReport, DiagnosticService
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result


@dataclass(frozen=True)
class RepairPlanAction:
    """A proposed repair action that is never executed by B29."""

    id: str
    diagnostic_code: str
    severity: str
    collection: str
    object_id: str = ""
    reference_id: str = ""
    message: str = ""
    proposed_action: str = ""
    impact: str = ""
    preflight: list[str] = field(default_factory=list)
    requires_backup_before_apply: bool = True
    mutates_project: bool = False
    source: str = "diagnostic"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "diagnostic_code": self.diagnostic_code,
            "severity": self.severity,
            "collection": self.collection,
            "object_id": self.object_id,
            "reference_id": self.reference_id,
            "message": self.message,
            "proposed_action": self.proposed_action,
            "impact": self.impact,
            "preflight": list(self.preflight),
            "requires_backup_before_apply": self.requires_backup_before_apply,
            "mutates_project": self.mutates_project,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RepairPlan:
    """Human-reviewable repair plan; it never applies changes."""

    project_id: str
    project_name: str
    actions: list[RepairPlanAction] = field(default_factory=list)
    mutates_project: bool = False
    requires_explicit_apply: bool = True
    requires_backup_before_apply: bool = True
    contract_version: str = "B29-repair-plan-v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "mutates_project": self.mutates_project,
            "requires_explicit_apply": self.requires_explicit_apply,
            "requires_backup_before_apply": self.requires_backup_before_apply,
            "actions": [action.to_dict() for action in self.actions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# Repair plan",
            "",
            f"Project: {self.project_name or self.project_id}",
            "",
            "No automatic mutation is performed by this plan.",
            "Any future apply operation requires explicit user approval and a backup first.",
            "",
            "## Actions",
        ]
        if not self.actions:
            lines.append("- No repair actions proposed.")
        for action in self.actions:
            lines.extend([
                f"- {action.id} — {action.diagnostic_code} [{action.severity}]",
                f"  - Collection: {action.collection or 'n/a'}",
                f"  - Object: {action.object_id or 'n/a'}",
                f"  - Reference: {action.reference_id or 'n/a'}",
                f"  - Proposed: {action.proposed_action}",
                f"  - Impact: {action.impact}",
                f"  - Preflight: {'; '.join(action.preflight)}",
            ])
        return "\n".join(lines)


class RepairPlanService:
    """Build non-destructive repair plans from diagnostics."""

    def __init__(self, diagnostic_service: DiagnosticService | None = None) -> None:
        self.diagnostic_service = diagnostic_service or DiagnosticService()

    def build_plan(self, project: Project) -> Result[RepairPlan, str]:
        """Diagnose *project* and generate a reviewable plan without mutation."""
        report_result = self.diagnostic_service.diagnose(project)
        if isinstance(report_result, Error):
            return Error(report_result.error)
        return self.build_plan_from_report(report_result.value)

    def build_plan_from_report(self, report: DiagnosticReport) -> Result[RepairPlan, str]:
        """Generate a plan from an existing diagnostic report."""
        actions = [
            self._action_from_item(index + 1, item)
            for index, item in enumerate([*report.items, *report.recommendations])
        ]
        return Ok(RepairPlan(
            project_id=report.project_id,
            project_name=report.project_name,
            actions=actions,
        ))

    def _action_from_item(self, index: int, item: DiagnosticItem) -> RepairPlanAction:
        proposed, impact, preflight = self._proposal_for(item)
        return RepairPlanAction(
            id=f"RP-{index:03d}",
            diagnostic_code=item.code,
            severity=item.severity.value,
            collection=item.collection,
            object_id=item.object_id,
            reference_id=item.reference_id,
            message=item.message,
            proposed_action=proposed,
            impact=impact,
            preflight=preflight,
            metadata=item.metadata,
        )

    def _proposal_for(self, item: DiagnosticItem) -> tuple[str, str, list[str]]:
        common = [
            "Run maintenance doctor immediately before applying any future repair.",
            "Create and validate a backup immediately before any future mutation.",
            "Review the proposed action with the user; do not infer canon creatively.",
        ]
        proposals: dict[str, tuple[str, str, list[str]]] = {
            "broken_relation_source": (
                "Reconnect relation source to an existing entity or archive the relation in a future approved repair.",
                "Would change or archive one relation only; canon impact requires human review.",
                [*common, "Verify replacement source entity exists and is visible to the author."],
            ),
            "broken_relation_target": (
                "Reconnect relation target to an existing entity or archive the relation in a future approved repair.",
                "Would change or archive one relation only; canon impact requires human review.",
                [*common, "Verify replacement target entity exists and is visible to the author."],
            ),
            "broken_issue_entity": (
                "Remove or replace the missing entity reference from the issue in a future approved repair.",
                "Would update issue references; does not alter entity canon.",
                [*common, "Verify the issue still describes a real problem after reference cleanup."],
            ),
            "broken_issue_relation": (
                "Remove or replace the missing relation reference from the issue in a future approved repair.",
                "Would update issue references; does not alter relation canon unless separately approved.",
                [*common, "Verify the relation replacement exists if one is chosen."],
            ),
            "broken_issue_source": (
                "Remove or replace the missing source reference from the issue in a future approved repair.",
                "Would update issue references; source text and canon remain unchanged.",
                [*common, "Verify original source provenance is not lost."],
            ),
            "obsolete_entity": (
                "Review obsolete entity and decide explicitly whether to keep, archive, supersede, or document debt.",
                "Would affect entity lifecycle only if a future approved action is executed.",
                [*common, "Check active relations and references before changing lifecycle state."],
            ),
        }
        if item.code in proposals:
            return proposals[item.code]
        if item.code.startswith("cleanup_") or item.code.startswith("review_"):
            return (
                "Review accumulated collection and prepare a compact/export/archive proposal; do not delete automatically.",
                "Future compacting could reduce project size but may affect traceability if not reviewed.",
                [*common, "Export the affected collection before any future compact/archive step."],
            )
        return (
            "Review manually and decide whether a future explicit repair ticket is needed.",
            "No direct impact in B29 because this plan is read-only.",
            common,
        )


__all__ = ["RepairPlan", "RepairPlanAction", "RepairPlanService"]
