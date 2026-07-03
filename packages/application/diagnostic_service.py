"""Read-only project integrity diagnostics for B29."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from packages.domain.candidate_issue import CandidateState, StructuredIssueState
from packages.domain.entity import CanonState
from packages.domain.project import Project
from packages.domain.result import Ok, Result


class DiagnosticSeverity(str, Enum):
    """Severity of a diagnostic finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class DiagnosticItem:
    """One read-only diagnostic finding or recommendation."""

    code: str
    severity: DiagnosticSeverity
    message: str
    collection: str = ""
    object_id: str = ""
    reference_id: str = ""
    mutates_project: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "collection": self.collection,
            "object_id": self.object_id,
            "reference_id": self.reference_id,
            "mutates_project": self.mutates_project,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DiagnosticReport:
    """Structured read-only diagnostic report."""

    project_id: str
    project_name: str
    schema_version: int | None
    counts: dict[str, int]
    size: dict[str, int]
    items: list[DiagnosticItem] = field(default_factory=list)
    recommendations: list[DiagnosticItem] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.items if item.severity == DiagnosticSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.items if item.severity == DiagnosticSeverity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "schema_version": self.schema_version,
            "counts": dict(self.counts),
            "size": dict(self.size),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "items": [item.to_dict() for item in self.items],
            "recommendations": [item.to_dict() for item in self.recommendations],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "## Diagnóstico de integridad",
            "",
            f"- Proyecto: {self.project_name or self.project_id}",
            f"- Errores: {self.error_count}",
            f"- Warnings: {self.warning_count}",
            "",
            "### Conteos",
        ]
        for key in sorted(self.counts):
            lines.append(f"- {key}: {self.counts[key]}")
        lines.extend(["", "### Hallazgos"])
        if not self.items:
            lines.append("- Sin hallazgos bloqueantes.")
        for item in self.items:
            lines.append(f"- [{item.severity.value}] {item.code}: {item.message}")
        lines.extend(["", "### Recomendaciones"])
        if not self.recommendations:
            lines.append("- Sin recomendaciones de limpieza.")
        for item in self.recommendations:
            lines.append(f"- [{item.severity.value}] {item.code}: {item.message}")
        return "\n".join(lines)


class DiagnosticService:
    """Read-only integrity, size and cleanup diagnostics for a Project."""

    CLEANUP_THRESHOLDS = {
        "history": 100,
        "candidates": 20,
        "issues": 20,
        "sources": 15,
    }

    COLLECTIONS = (
        "entities",
        "relations",
        "sources",
        "history",
        "issues",
        "candidates",
        "writing_units",
        "campaigns",
        "player_character_profiles",
        "campaign_clocks",
        "secrets",
        "clues",
        "factions",
        "fronts",
        "sessions",
        "saved_graph_views",
    )

    def diagnose(self, project: Project) -> Result[DiagnosticReport, str]:
        """Build a structured report without mutating the project."""
        data = project.to_dict()
        counts = self._counts(project)
        items = self._integrity_items(project)
        recommendations = self._cleanup_recommendations(project, counts)
        report = DiagnosticReport(
            project_id=project.id,
            project_name=project.name,
            schema_version=data.get("schema_version"),
            counts=counts,
            size={
                "serialized_json_bytes": len(json.dumps(data, ensure_ascii=False).encode("utf-8")),
                "collection_count": len(counts),
            },
            items=items,
            recommendations=recommendations,
        )
        return Ok(report)

    def _counts(self, project: Project) -> dict[str, int]:
        return {
            name: len(getattr(project, name, []) or [])
            for name in self.COLLECTIONS
            if hasattr(project, name)
        }

    def _integrity_items(self, project: Project) -> list[DiagnosticItem]:
        items: list[DiagnosticItem] = []
        entity_ids = {entity.id for entity in project.entities}
        relation_ids = {relation.id for relation in project.relations}
        source_ids = {source.id for source in project.sources}

        for relation in project.relations:
            if relation.source_id not in entity_ids:
                items.append(DiagnosticItem(
                    code="broken_relation_source",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Relation {relation.id} references missing source entity {relation.source_id}",
                    collection="relations",
                    object_id=relation.id,
                    reference_id=relation.source_id,
                ))
            if relation.target_id not in entity_ids:
                items.append(DiagnosticItem(
                    code="broken_relation_target",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Relation {relation.id} references missing target entity {relation.target_id}",
                    collection="relations",
                    object_id=relation.id,
                    reference_id=relation.target_id,
                ))

        for issue in project.issues:
            for entity_id in getattr(issue, "affected_entity_ids", []) or []:
                if entity_id and entity_id not in entity_ids:
                    items.append(DiagnosticItem(
                        code="broken_issue_entity",
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Issue {issue.id} references missing entity {entity_id}",
                        collection="issues",
                        object_id=issue.id,
                        reference_id=entity_id,
                    ))
            for relation_id in getattr(issue, "affected_relation_ids", []) or []:
                if relation_id and relation_id not in relation_ids:
                    items.append(DiagnosticItem(
                        code="broken_issue_relation",
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Issue {issue.id} references missing relation {relation_id}",
                        collection="issues",
                        object_id=issue.id,
                        reference_id=relation_id,
                    ))
            for source_id in getattr(issue, "affected_source_ids", []) or []:
                if source_id and source_id not in source_ids:
                    items.append(DiagnosticItem(
                        code="broken_issue_source",
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Issue {issue.id} references missing source {source_id}",
                        collection="issues",
                        object_id=issue.id,
                        reference_id=source_id,
                    ))

        for entity in project.entities:
            if entity.canon_state == CanonState.OBSOLETO:
                items.append(DiagnosticItem(
                    code="obsolete_entity",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Entity {entity.id} is marked obsolete and may need review",
                    collection="entities",
                    object_id=entity.id,
                ))
        return items

    def _cleanup_recommendations(self, project: Project, counts: dict[str, int]) -> list[DiagnosticItem]:
        recommendations: list[DiagnosticItem] = []
        if counts.get("history", 0) > self.CLEANUP_THRESHOLDS["history"]:
            recommendations.append(self._recommendation(
                "cleanup_history", "history", counts["history"],
                "Historial voluminoso: considerar exportar/compactar con backup previo.",
            ))

        pending_candidates = sum(
            1 for candidate in project.candidates
            if getattr(candidate, "state", None) == CandidateState.PENDIENTE
        )
        if pending_candidates > self.CLEANUP_THRESHOLDS["candidates"]:
            recommendations.append(self._recommendation(
                "review_pending_candidates", "candidates", pending_candidates,
                "Candidatos pendientes acumulados: revisar, archivar o posponer explícitamente.",
            ))

        open_issues = sum(
            1 for issue in project.issues
            if getattr(issue, "state", None) == StructuredIssueState.ABIERTA
        )
        if open_issues > self.CLEANUP_THRESHOLDS["issues"]:
            recommendations.append(self._recommendation(
                "review_open_issues", "issues", open_issues,
                "Incidencias abiertas acumuladas: revisar y resolver o descartar explícitamente.",
            ))

        if counts.get("sources", 0) > self.CLEANUP_THRESHOLDS["sources"]:
            recommendations.append(self._recommendation(
                "cleanup_sources", "sources", counts["sources"],
                "Fuentes/documentos acumulados: considerar consolidación no destructiva.",
            ))
        return recommendations

    def _recommendation(self, code: str, collection: str, count: int, message: str) -> DiagnosticItem:
        return DiagnosticItem(
            code=code,
            severity=DiagnosticSeverity.INFO,
            message=message,
            collection=collection,
            metadata={"count": count, "requires_backup_before_future_mutation": True},
            mutates_project=False,
        )


__all__ = [
    "DiagnosticItem",
    "DiagnosticReport",
    "DiagnosticSeverity",
    "DiagnosticService",
]
