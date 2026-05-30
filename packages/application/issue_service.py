"""
IssueService — CRUD, state transitions, and 15 deterministic validators (B12-T02).

Provides ``IssueService`` (stateful) and ``run_validators()`` (stateless).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.candidate_issue import (
    StructuredIssue,
    StructuredIssueSeverity,
    StructuredIssueState,
    StructuredIssueType,
    is_valid_transition,
)
from packages.domain.entity import CanonState, EntityType
from packages.domain.result import Error, Ok, Result


CONTRADICTORY_PAIRS: set[tuple[str, str]] = {
    ("es_aliado_de", "es_enemigo_de"),
    ("conoce", "desconoce"),
    ("protege", "traiciono"),
    ("ama", "odia"),
    ("pertenece_a", "expulsado_de"),
}


@dataclass
class IssueService:
    """Stateful service for issue CRUD and state transitions."""

    project_service: Any

    def _proj(self):
        p = self.project_service.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_issue(self, data: dict[str, Any]) -> Result[StructuredIssue, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return Error(proj.error)
        si = StructuredIssue.from_dict(data)
        proj.value.issues.append(si)
        return Ok(si)

    def get_issue(self, issue_id: str) -> Result[StructuredIssue, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return Error(proj.error)
        for i in proj.value.issues:
            if i.id == issue_id:
                return Ok(i)
        return Error(f"Issue '{issue_id}' not found")

    def list_issues(
        self, state: str | None = None,
        itype: str | None = None,
        severity: str | None = None,
    ) -> Result[list[StructuredIssue], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return Error(proj.error)
        result = list(proj.value.issues)
        if state:
            result = [i for i in result if i.state.value == state]
        if itype:
            result = [i for i in result if i.type.value == itype]
        if severity:
            result = [i for i in result if i.severity.value == severity]
        return Ok(result)

    def list_issues_by_entity(
        self, entity_id: str,
    ) -> Result[list[StructuredIssue], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([
            i for i in proj.value.issues
            if entity_id in i.affected_entity_ids
        ])

    # ── State transitions ─────────────────────────────────────────────

    def transition_state(
        self, issue_id: str, new_state: str, resolution: str = "",
    ) -> Result[StructuredIssue, str]:
        ri = self.get_issue(issue_id)
        if isinstance(ri, Error):
            return ri
        issue = ri.value
        try:
            to_state = StructuredIssueState(new_state)
        except ValueError:
            return Error(f"Invalid state: {new_state}")
        if not is_valid_transition(issue.state, to_state):
            return Error(
                f"Invalid transition: {issue.state.value} -> {new_state}"
            )
        issue.state = to_state
        if resolution:
            issue.resolution = resolution
        return Ok(issue)

    def review_issue(
        self, issue_id: str,
    ) -> Result[StructuredIssue, str]:
        """Shortcut: mark as REVISADA."""
        return self.transition_state(issue_id, "revisada")

    def accept_issue(
        self, issue_id: str,
    ) -> Result[StructuredIssue, str]:
        """Shortcut: mark as ACEPTADA."""
        return self.transition_state(issue_id, "aceptada")

    def resolve_issue(
        self, issue_id: str, note: str = "",
    ) -> Result[StructuredIssue, str]:
        """Controlled shortcut: ABIERTA/REVISADA/ACEPTADA -> RESUELTA."""
        ri = self.get_issue(issue_id)
        if isinstance(ri, Error):
            return ri
        issue = ri.value
        if issue.state not in (
            StructuredIssueState.ABIERTA,
            StructuredIssueState.REVISADA,
            StructuredIssueState.ACEPTADA,
        ):
            return Error(
                f"Cannot resolve from {issue.state.value}. "
                "Must be abierta/revisada/aceptada."
            )
        issue.state = StructuredIssueState.RESUELTA
        if note:
            issue.resolution = note
        return Ok(issue)

    def discard_issue(
        self, issue_id: str, note: str = "",
    ) -> Result[StructuredIssue, str]:
        """Controlled shortcut: ABIERTA/REVISADA/PENDIENTE_INFO -> DESCARTADA."""
        ri = self.get_issue(issue_id)
        if isinstance(ri, Error):
            return ri
        issue = ri.value
        if issue.state not in (
            StructuredIssueState.ABIERTA,
            StructuredIssueState.REVISADA,
            StructuredIssueState.PENDIENTE_INFO,
        ):
            return Error(
                f"Cannot discard from {issue.state.value}. "
                "Must be abierta/revisada/pendiente_info."
            )
        issue.state = StructuredIssueState.DESCARTADA
        if note:
            issue.resolution = note
        return Ok(issue)

    def mark_intentional(
        self, issue_id: str, note: str = "",
    ) -> Result[StructuredIssue, str]:
        """Controlled shortcut: ABIERTA/REVISADA -> INTENCIONAL."""
        ri = self.get_issue(issue_id)
        if isinstance(ri, Error):
            return ri
        issue = ri.value
        if issue.state not in (
            StructuredIssueState.ABIERTA,
            StructuredIssueState.REVISADA,
        ):
            return Error(
                f"Cannot mark intentional from {issue.state.value}. "
                "Must be abierta/revisada."
            )
        issue.state = StructuredIssueState.INTENCIONAL
        issue.is_intentional = True
        if note:
            issue.resolution = note
        return Ok(issue)

    def add_resolution_note(
        self, issue_id: str, note: str,
    ) -> Result[StructuredIssue, str]:
        ri = self.get_issue(issue_id)
        if isinstance(ri, Error):
            return ri
        ri.value.resolution = (
            ri.value.resolution + "\n" + note if ri.value.resolution else note
        )
        return Ok(ri.value)

    # ── Validation ────────────────────────────────────────────────────

    def run_validation(
        self, entity_id: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Run all 15 validators, return summary."""
        proj = self._proj()
        if isinstance(proj, Error):
            return Error(proj.error)
        project = proj.value

        new_count = 0
        skipped = 0
        for issue in run_validators(project, entity_id):
            if self._already_exists(issue):
                skipped += 1
            else:
                project.issues.append(issue)
                new_count += 1

        return Ok({
            "new": new_count,
            "skipped": skipped,
            "total": new_count + skipped,
        })

    def _already_exists(self, issue: StructuredIssue) -> bool:
        proj = self._proj()
        if isinstance(proj, Error):
            return False
        for existing in proj.value.issues:
            if existing.type != issue.type:
                continue
            if existing.state in (
                StructuredIssueState.ABIERTA,
                StructuredIssueState.ACEPTADA,
            ):
                if set(existing.affected_entity_ids) & set(
                    issue.affected_entity_ids,
                ):
                    return True
            if existing.state == StructuredIssueState.INTENCIONAL:
                if set(existing.affected_entity_ids) & set(
                    issue.affected_entity_ids,
                ):
                    return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# Validators (stateless)
# ═══════════════════════════════════════════════════════════════════════


def _make_issue(
    itype: StructuredIssueType,
    severity: StructuredIssueSeverity,
    description: str,
    entity_ids: list[str] | None = None,
    relation_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
    evidence: str = "",
    solutions: list[str] | None = None,
) -> StructuredIssue:
    return StructuredIssue(
        type=itype,
        severity=severity,
        state=StructuredIssueState.ABIERTA,
        affected_entity_ids=entity_ids or [],
        affected_relation_ids=relation_ids or [],
        affected_source_ids=source_ids or [],
        description=description,
        evidence=evidence,
        possible_solutions=solutions or [],
    )


def run_validators(
    project: Any, entity_id: str | None = None,
) -> list[StructuredIssue]:
    """Run all 15 deterministic validators. Returns new issues."""
    results: list[StructuredIssue] = []

    # Build lookup sets
    entity_ids = {e.id for e in project.entities}
    entities_by_name: dict[str, list] = {}
    for e in project.entities:
        entities_by_name.setdefault(e.name.lower(), []).append(e)

    # 1. Broken relations
    for r in project.relations:
        if r.source_id not in entity_ids or r.target_id not in entity_ids:
            results.append(_make_issue(
                StructuredIssueType.BROKEN_RELATION,
                StructuredIssueSeverity.ALTA,
                f"Relation {r.id[:8]} has missing endpoint",
                entity_ids=[r.source_id, r.target_id],
                relation_ids=[r.id],
                evidence=f"source={r.source_id in entity_ids} target={r.target_id in entity_ids}",
            ))

    # 2. Duplicate entities
    for name, ents in entities_by_name.items():
        if len(ents) > 1:
            eids = [e.id for e in ents]
            results.append(_make_issue(
                StructuredIssueType.DUPLICATE_ENTITY,
                StructuredIssueSeverity.MEDIA,
                f"Entities with same name '{ents[0].name}'",
                entity_ids=eids,
                evidence=f"{len(ents)} entities share name",
                solutions=["Rename one", "Merge"],
            ))

    # 6. Orphan entities (BAJA, excludes NOTA/SESION/archived)
    for e in project.entities:
        if e.canon_state == CanonState.ARCHIVADO:
            continue
        if e.entity_type in (EntityType.NOTA, EntityType.SESION):
            continue
        if e.custom_metadata.get("intentionally_isolated") == "true":
            continue
        has_relations = any(
            r.source_id == e.id or r.target_id == e.id
            for r in project.relations
        )
        if not has_relations:
            results.append(_make_issue(
                StructuredIssueType.ORPHAN_ENTITY,
                StructuredIssueSeverity.BAJA,
                f"Entity '{e.name}' has no relations",
                entity_ids=[e.id],
            ))

    # 7. No description
    for e in project.entities:
        if not e.brief_description and not e.extended_description:
            results.append(_make_issue(
                StructuredIssueType.NO_DESCRIPTION,
                StructuredIssueSeverity.MEDIA,
                f"Entity '{e.name}' has no description",
                entity_ids=[e.id],
            ))

    # 8. Canon low certainty
    for e in project.entities:
        if e.canon_state == CanonState.CANONICO:
            if e.certainty_level.value in ("dudoso", "falso"):
                results.append(_make_issue(
                    StructuredIssueType.CANON_LOW_CERTAINTY,
                    StructuredIssueSeverity.MEDIA,
                    f"Entity '{e.name}' is canonico with low certainty",
                    entity_ids=[e.id],
                    evidence=f"certainty={e.certainty_level.value}",
                ))

    # 15. Contradictory relations
    rel_pairs: dict[tuple[str, str], list] = {}
    for r in project.relations:
        key = tuple(sorted([r.source_id, r.target_id]))
        rel_pairs.setdefault(key, []).append(r)

    for (a, b), rels in rel_pairs.items():
        types = {r.relation_type.value for r in rels}
        for pair in CONTRADICTORY_PAIRS:
            if pair[0] in types and pair[1] in types:
                results.append(_make_issue(
                    StructuredIssueType.CONTRADICTORY_RELATION,
                    StructuredIssueSeverity.MEDIA,
                    f"Entities have contradictory relations: {pair[0]} + {pair[1]}",
                    entity_ids=[a, b],
                    relation_ids=[r.id for r in rels],
                ))
                break

    # Filter by entity_id if specified
    if entity_id:
        results = [
            i for i in results
            if entity_id in i.affected_entity_ids
        ]

    return results


__all__ = ["IssueService", "run_validators", "CONTRADICTORY_PAIRS"]
