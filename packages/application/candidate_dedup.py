"""Candidate Deduplication — B42-T10.

Detects duplicate candidates before showing them to the user:
- Same name/type as existing entities
- Already-existing relations
- Duplicate pending candidates

Marks as possible duplicate but NEVER auto-deletes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeduplicationResult:
    """Result of deduplication check on a single candidate."""
    candidate: dict[str, Any]
    is_possible_duplicate: bool = False
    reason: str = ""


class CandidateDeduplicator:
    """Check candidates against existing entities, relations, and pending items.

    Usage:
        dedup = CandidateDeduplicator.from_project(project, pending_candidates)
        results = dedup.check_batch(new_candidates)
        for r in results:
            if r.is_possible_duplicate:
                show_warning(r.reason)
    """

    def __init__(
        self,
        existing_names: set[str] | None = None,
        existing_relations: set[tuple[str, str, str]] | None = None,
        pending_names: set[str] | None = None,
        pending_relations: set[tuple[str, str, str]] | None = None,
    ):
        # Normalize to lowercase for case-insensitive matching
        self.existing_names = {n.lower() for n in (existing_names or set())}
        self.existing_relations = existing_relations or set()
        self.pending_names = {n.lower() for n in (pending_names or set())}
        self.pending_relations = pending_relations or set()

    def check(self, candidate: dict[str, Any]) -> DeduplicationResult:
        """Check a single candidate for duplicates.

        Returns a result with is_possible_duplicate=True if any match found.
        The candidate is NEVER removed — only flagged.
        """
        reasons = []

        # Check entity name duplicate
        name = candidate.get("name", "")
        if name and name.lower() in self.existing_names:
            reasons.append(f"Nombre '{name}' ya existe como entidad")

        # Check pending name duplicate
        if name and name.lower() in self.pending_names:
            reasons.append(f"Nombre '{name}' ya existe como candidato pendiente")

        # Check relation duplicate
        source = candidate.get("source_name", candidate.get("source_id", ""))
        target = candidate.get("target_name", candidate.get("target_id", ""))
        rel_type = candidate.get("relation_type", "")
        if source and target and rel_type:
            rel_key = (str(source), str(rel_type), str(target))
            if rel_key in self.existing_relations:
                reasons.append(f"Relación {source}—{rel_type}—{target} ya existe")
            if rel_key in self.pending_relations:
                reasons.append(f"Relación {source}—{rel_type}—{target} ya pendiente")

        return DeduplicationResult(
            candidate=candidate,
            is_possible_duplicate=len(reasons) > 0,
            reason="; ".join(reasons),
        )

    def check_batch(self, candidates: list[dict[str, Any]]) -> list[DeduplicationResult]:
        """Check multiple candidates. Returns results in same order."""
        return [self.check(c) for c in candidates]

    @classmethod
    def from_project(cls, project, pending_candidates: list | None = None) -> CandidateDeduplicator:
        """Build deduplicator from a live Project object.

        Extracts entity names and relation tuples for comparison.
        """
        existing_names = set()
        existing_relations = set()

        if project:
            # Extract entity names
            for entity in getattr(project, "entities", []):
                if hasattr(entity, "name"):
                    existing_names.add(entity.name)

            # Extract relation tuples
            for rel in getattr(project, "relations", []):
                src_name = ""
                tgt_name = ""
                if hasattr(rel, "source_id") and hasattr(rel, "relation_type") and hasattr(rel, "target_id"):
                    # Try to resolve names from entity IDs
                    entity_map = {e.id: e.name for e in getattr(project, "entities", []) if hasattr(e, "id") and hasattr(e, "name")}
                    src_name = entity_map.get(rel.source_id, rel.source_id)
                    tgt_name = entity_map.get(rel.target_id, rel.target_id)
                    existing_relations.add((src_name, str(rel.relation_type.value if hasattr(rel.relation_type, "value") else rel.relation_type), tgt_name))

        pending_names = set()
        pending_relations = set()
        for cand in (pending_candidates or []):
            name = cand.get("entity_name", cand.get("name", ""))
            if name:
                pending_names.add(name)
            src = cand.get("source_name", cand.get("source_id", ""))
            tgt = cand.get("target_name", cand.get("target_id", ""))
            rt = cand.get("relation_type", "")
            if src and tgt and rt:
                pending_relations.add((str(src), str(rt), str(tgt)))

        return cls(
            existing_names=existing_names,
            existing_relations=existing_relations,
            pending_names=pending_names,
            pending_relations=pending_relations,
        )
