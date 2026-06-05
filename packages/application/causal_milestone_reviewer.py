"""Causal milestone candidate reviewer — B41-T06.

Reviews a proposed milestone against the project context and returns a list
of ReviewFinding objects. Never mutates the project or canon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus


class ReviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ReviewFinding:
    label: str
    severity: ReviewSeverity
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "label": self.label,
            "severity": self.severity.value,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewFinding:
        return cls(
            label=data.get("label", ""),
            severity=ReviewSeverity(data.get("severity", "info")),
            detail=data.get("detail", ""),
        )


def review_causal_milestone(
    milestone: CausalMilestone,
    project: Any,
) -> list[ReviewFinding]:
    """Review a milestone candidate against project context.

    Checks:
    - Orphan: no affected entities, relations, or parent hitos.
    - Weak causality: no caused relations and no child hitos.
    - Contradiction: parent milestone describes opposite state.
    - Redundancy: another milestone already covers similar ground.
    """
    findings: list[ReviewFinding] = []

    has_entities = bool(milestone.affected_entity_ids)
    has_relations = bool(milestone.caused_relation_ids)
    has_parents = bool(milestone.causal_parent_hito_ids)
    has_children = bool(milestone.causal_child_hito_ids)

    # ── Orphan detection ──
    if not has_entities and not has_relations and not has_parents:
        findings.append(ReviewFinding(
            label="Hito huérfano",
            severity=ReviewSeverity.WARNING,
            detail="No tiene hojas afectadas, relaciones causadas ni hitos causa. Considerar vincularlo al grafo.",
        ))

    # ── Weak causality ──
    if not has_relations and not has_children:
        findings.append(ReviewFinding(
            label="Causalidad débil",
            severity=ReviewSeverity.INFO,
            detail="No causa relaciones ni tiene hitos consecuencia. Podría quedar como antecedente sin efecto visible.",
        ))

    # ── Contradiction with parents ──
    if has_parents and project is not None:
        existing_hitos = {h.id: h for h in getattr(project, "causal_milestones", []) or []}
        for parent_id in milestone.causal_parent_hito_ids:
            parent = existing_hitos.get(parent_id)
            if parent is None:
                continue
            # Simple heuristic: if parent description contains negation of key milestone concepts
            parent_desc = (getattr(parent, "description", "") or "").lower()
            own_desc = (getattr(milestone, "description", "") or "").lower()
            if _has_contradiction_keywords(parent_desc, own_desc):
                findings.append(ReviewFinding(
                    label="Posible contradicción con hito causa",
                    severity=ReviewSeverity.WARNING,
                    detail=f"El hito causa '{getattr(parent, 'title', parent_id[:8])}' describe '{parent_desc[:60]}' "
                           f"mientras este hito describe '{own_desc[:60]}'. Verificar coherencia.",
                ))

    # ── Redundancy check ──
    if project is not None:
        own_title_lower = milestone.title.lower() if milestone.title else ""
        for existing in getattr(project, "causal_milestones", []) or []:
            if existing.id == milestone.id:
                continue
            existing_title = getattr(existing, "title", "").lower()
            if own_title_lower and existing_title and (
                own_title_lower in existing_title or existing_title in own_title_lower
            ):
                findings.append(ReviewFinding(
                    label="Posible redundancia",
                    severity=ReviewSeverity.INFO,
                    detail=f"Ya existe un hito con título similar: '{getattr(existing, 'title', '')}'.",
                ))
                break

    return findings


def _has_contradiction_keywords(text_a: str, text_b: str) -> bool:
    """Simple heuristic for detecting contradiction between two texts."""
    contradiction_pairs = [
        ("paz", "guerra"),
        ("guerra", "paz"),
        ("vida", "muerte"),
        ("muerte", "vida"),
        ("unión", "ruptura"),
        ("union", "ruptura"),
        ("nunca hubo", ""),
        ("nunca existió", ""),
    ]
    for word_a, word_b in contradiction_pairs:
        if word_a in text_a and word_b and word_b in text_b:
            return True
        if word_b and word_b in text_a and word_a in text_b:
            return True
        # Handle "nunca X" pattern: text_a denies X, text_b affirms X
        if not word_b and word_a in text_a:
            # Extract the keyword after the denial phrase
            remainder = text_a.split(word_a)[-1].strip()
            # Check if that remainder overlaps significantly with text_b
            remaining_words = [w for w in remainder.split() if len(w) > 3]
            if any(w in text_b for w in remaining_words):
                return True
    return False
