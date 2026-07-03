"""Narrative corpus indexer for E03.

The indexer reads the domain Project directly and builds an in-memory corpus
index for later RAG retrieval. It does not call AI providers, create embeddings,
persist data, or mutate canon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
import hashlib
import json
import re

from packages.application.context_sanitizer import sanitize_nested
from packages.application.narrative_rag_contract import (
    ContextItem,
    ContextPriority,
    CorpusItemKind,
)


BRANCH_ENTITY_TYPES: frozenset[str] = frozenset({
    "faccion",
    "cultura",
    "sistema_magico",
    "religion",
    "institucion",
    "trama",
    "contenedor",
})

ARCHIVED_CANON_STATES: frozenset[str] = frozenset({
    "archivado",
    "descartado",
    "obsoleto",
})

PRIVATE_VISIBILITY_STATES: frozenset[str] = frozenset({
    "privado_autor",
    "secreto_mundo",
    "preparado_no_revelado",
})

ACCEPTED_CANDIDATE_STATES: frozenset[str] = frozenset({
    "aceptado",
    "editado_aceptado",
    "fusionado",
    "parcialmente_aceptado",
})

PENDING_CANDIDATE_STATES: frozenset[str] = frozenset({
    "pendiente",
    "pospuesto",
    "requiere_revision",
})

REJECTED_CANDIDATE_STATES: frozenset[str] = frozenset({
    "rechazado",
    "archivado",
})


@dataclass(frozen=True)
class IndexingOptions:
    include_pending_candidates: bool = False
    include_rejected_candidates: bool = False
    # Accepted candidates duplicate the canon they created (entity/world_layer/…),
    # which is indexed on its own. RAG context sets this False so deleted canon
    # cannot resurface through its lingering accepted-candidate record.
    include_accepted_candidates: bool = True
    audience: str = "gm"


@dataclass(frozen=True)
class CorpusIndexRecord:
    kind: CorpusItemKind
    ref_id: str
    source: str
    rendered_text: str
    content_hash: str
    tokens_estimated: int
    references: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""
    indexed_at: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.ref_id}"

    def to_context_item(
        self,
        *,
        score: float = 1.0,
        reason: str = "indexed_corpus",
        priority: ContextPriority = ContextPriority.NORMAL,
    ) -> ContextItem:
        return ContextItem(
            kind=self.kind,
            ref_id=self.ref_id,
            source=self.source,
            score=score,
            reason=reason,
            priority=priority,
            tokens_estimated=self.tokens_estimated,
            rendered_text=self.rendered_text,
            references=list(self.references),
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "ref_id": self.ref_id,
            "source": self.source,
            "rendered_text": self.rendered_text,
            "content_hash": self.content_hash,
            "tokens_estimated": self.tokens_estimated,
            "references": list(self.references),
            "metadata": dict(self.metadata),
            "updated_at": self.updated_at,
            "indexed_at": self.indexed_at,
        }


@dataclass(frozen=True)
class CorpusIndexStats:
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "by_kind": dict(self.by_kind),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class NarrativeCorpusIndex:
    project_id: str
    records: dict[str, CorpusIndexRecord] = field(default_factory=dict)
    stats: CorpusIndexStats = field(default_factory=CorpusIndexStats)
    updated_at: str = ""

    def __len__(self) -> int:
        return len(self.records)

    def get(self, kind: CorpusItemKind | str, ref_id: str) -> CorpusIndexRecord | None:
        kind_value = kind.value if isinstance(kind, CorpusItemKind) else str(kind)
        return self.records.get(f"{kind_value}:{ref_id}")

    def items(self, kind: CorpusItemKind | str | None = None) -> list[CorpusIndexRecord]:
        if kind is None:
            return sorted(self.records.values(), key=lambda item: item.key)
        kind_value = kind.value if isinstance(kind, CorpusItemKind) else str(kind)
        return sorted(
            [item for item in self.records.values() if item.kind.value == kind_value],
            key=lambda item: item.key,
        )

    def counts_by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records.values():
            counts[record.kind.value] = counts.get(record.kind.value, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "updated_at": self.updated_at,
            "stats": self.stats.to_dict(),
            "records": [record.to_dict() for record in self.items()],
        }


class CorpusIndexer:
    """Build and incrementally refresh an in-memory narrative corpus index."""

    def index_project(
        self,
        project: Any,
        *,
        previous_index: NarrativeCorpusIndex | None = None,
        options: IndexingOptions | None = None,
    ) -> NarrativeCorpusIndex:
        options = options or IndexingOptions()
        indexed_at = _now_iso()
        previous_records = previous_index.records if previous_index is not None else {}
        built_records = list(self._build_records(project, options, indexed_at=indexed_at))

        records: dict[str, CorpusIndexRecord] = {}
        created = updated = unchanged = 0
        for record in built_records:
            previous = previous_records.get(record.key)
            if previous is not None and previous.content_hash == record.content_hash:
                records[record.key] = previous
                unchanged += 1
            else:
                records[record.key] = record
                if previous is None:
                    created += 1
                else:
                    updated += 1

        removed = len(set(previous_records) - set(records))
        warnings: list[str] = []
        if len(records) > 50:
            warnings.append("large_corpus_indexed_synchronously")
        stats = CorpusIndexStats(
            total=len(records),
            created=created,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            by_kind=_counts_by_kind(records.values()),
            warnings=warnings,
        )
        return NarrativeCorpusIndex(
            project_id=str(getattr(project, "id", "")),
            records=records,
            stats=stats,
            updated_at=indexed_at,
        )

    def _build_records(
        self,
        project: Any,
        options: IndexingOptions,
        *,
        indexed_at: str,
    ) -> Iterable[CorpusIndexRecord]:
        entities = list(getattr(project, "entities", []) or [])
        relations = list(getattr(project, "relations", []) or [])
        entity_by_id = {str(getattr(entity, "id", "")): entity for entity in entities}
        layer_by_id = {str(getattr(layer, "id", "")): layer for layer in (getattr(project, "world_layers", []) or [])}
        parent_map, child_map = _contains_maps(relations)

        for entity in entities:
            if not _indexable_state(entity, options.audience):
                continue
            kind = CorpusItemKind.BRANCH if _is_branch_entity(entity) else CorpusItemKind.ENTITY
            yield _make_record(
                kind=kind,
                ref_id=str(getattr(entity, "id", "")),
                source="project.entities",
                rendered_text=_render_entity(entity, kind, entity_by_id, layer_by_id, parent_map, child_map),
                references=_entity_references(entity, parent_map),
                metadata=_entity_metadata(entity, kind, parent_map, child_map),
                updated_at=_string_value(getattr(entity, "updated_at", "")),
                indexed_at=indexed_at,
            )

        for relation in relations:
            if not _indexable_state(relation, options.audience):
                continue
            yield _make_record(
                kind=CorpusItemKind.RELATION,
                ref_id=str(getattr(relation, "id", "")),
                source="project.relations",
                rendered_text=_render_relation(relation, entity_by_id, layer_by_id),
                references=_relation_references(relation),
                metadata=_relation_metadata(relation),
                updated_at=_string_value(getattr(relation, "updated_at", "")),
                indexed_at=indexed_at,
            )

        for layer in getattr(project, "world_layers", []) or []:
            if not bool(getattr(layer, "is_visible", True)):
                continue
            yield _make_record(
                kind=CorpusItemKind.WORLD_LAYER,
                ref_id=str(getattr(layer, "id", "")),
                source="project.world_layers",
                rendered_text=_render_world_layer(layer, entity_by_id, relations),
                references=_layer_references(layer, entities),
                metadata=_layer_metadata(layer),
                updated_at="",
                indexed_at=indexed_at,
            )

        for milestone in getattr(project, "causal_milestones", []) or []:
            if _enum_value(getattr(milestone, "status", "")) in {"rejected", "archived"}:
                continue
            if not _visibility_allowed(getattr(milestone, "visibility_state", ""), options.audience):
                continue
            yield _make_record(
                kind=CorpusItemKind.MILESTONE,
                ref_id=str(getattr(milestone, "id", "")),
                source="project.causal_milestones",
                rendered_text=_render_milestone(milestone, entity_by_id, layer_by_id),
                references=_milestone_references(milestone),
                metadata=_milestone_metadata(milestone),
                updated_at=_string_value(getattr(milestone, "updated_at", "")),
                indexed_at=indexed_at,
            )

        chronology = getattr(project, "project_chronology", None)
        if chronology is not None and _chronology_has_content(chronology):
            yield _make_record(
                kind=CorpusItemKind.CHRONOLOGY,
                ref_id=str(getattr(chronology, "id", "project_chronology") or "project_chronology"),
                source="project.project_chronology",
                rendered_text=_render_chronology(chronology),
                references=[f"milestone:{mid}" for mid in getattr(chronology, "milestone_ids", []) or []],
                metadata=_safe_metadata(getattr(chronology, "metadata", {}) or {}),
                updated_at=_string_value(getattr(chronology, "updated_at", "")),
                indexed_at=indexed_at,
            )

        for candidate in getattr(project, "candidates", []) or []:
            if not _candidate_included(candidate, options):
                continue
            yield _make_record(
                kind=CorpusItemKind.CANDIDATE,
                ref_id=str(getattr(candidate, "id", "")),
                source="project.candidates",
                rendered_text=_render_candidate(candidate),
                references=_candidate_references(candidate),
                metadata=_candidate_metadata(candidate),
                updated_at=_string_value(getattr(candidate, "reviewed_at", "") or getattr(candidate, "created_at", "")),
                indexed_at=indexed_at,
            )

        for issue in getattr(project, "issues", []) or []:
            yield _make_record(
                kind=CorpusItemKind.ISSUE,
                ref_id=str(getattr(issue, "id", "")),
                source="project.issues",
                rendered_text=_render_issue(issue),
                references=_issue_references(issue),
                metadata=_issue_metadata(issue),
                updated_at=_string_value(getattr(issue, "reviewed_at", "") or getattr(issue, "detected_at", "")),
                indexed_at=indexed_at,
            )

        creative = _creative_record(project, indexed_at)
        if creative is not None:
            yield creative


def _make_record(
    *,
    kind: CorpusItemKind,
    ref_id: str,
    source: str,
    rendered_text: str,
    references: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    updated_at: str = "",
    indexed_at: str,
) -> CorpusIndexRecord:
    safe_metadata = _safe_metadata(metadata or {})
    safe_metadata.setdefault("source_type", "canon")
    safe_references = [ref for ref in (references or []) if ref]
    content_hash = _content_hash(kind, ref_id, rendered_text, safe_references, safe_metadata)
    return CorpusIndexRecord(
        kind=kind,
        ref_id=ref_id,
        source=source,
        rendered_text=rendered_text,
        content_hash=content_hash,
        tokens_estimated=_estimate_tokens(rendered_text),
        references=safe_references,
        metadata=safe_metadata,
        updated_at=updated_at,
        indexed_at=indexed_at,
    )


def _render_entity(
    entity: Any,
    kind: CorpusItemKind,
    entity_by_id: dict[str, Any],
    layer_by_id: dict[str, Any],
    parent_map: dict[str, list[str]],
    child_map: dict[str, list[str]],
) -> str:
    entity_id = str(getattr(entity, "id", ""))
    parent_names = [_name(entity_by_id.get(pid), pid) for pid in parent_map.get(entity_id, [])]
    child_names = [_name(entity_by_id.get(cid), cid) for cid in child_map.get(entity_id, [])]
    layers = [_name(layer_by_id.get(lid), lid) for lid in _str_list(getattr(entity, "layer_ids", []))]
    metadata = getattr(entity, "custom_metadata", {}) or {}
    tree_rules = _str_list(metadata.get("tree_internal_rules"))
    tree_questions = _str_list(metadata.get("tree_open_questions"))

    lines = [
        _line("Kind", "Branch" if kind == CorpusItemKind.BRANCH else "Entity"),
        _line("Name", getattr(entity, "name", "")),
        _line("Type", _enum_value(getattr(entity, "entity_type", ""))),
        _line("Summary", getattr(entity, "brief_description", "")),
        _line("Body", getattr(entity, "extended_description", "")),
        _line("Exportable notes", getattr(entity, "exportable_notes", "")),
        _line("Tags", ", ".join(_str_list(getattr(entity, "tags", [])))),
        _line("Layers", ", ".join(layers)),
        _line("Parent branches", ", ".join(parent_names)),
        _line("Members", ", ".join(child_names)),
        _line("Branch rules", "; ".join(tree_rules)),
        _line("Branch open questions", "; ".join(tree_questions)),
    ]
    return _join_lines(lines)


def _render_relation(relation: Any, entity_by_id: dict[str, Any], layer_by_id: dict[str, Any]) -> str:
    source_id = str(getattr(relation, "source_id", ""))
    target_id = str(getattr(relation, "target_id", ""))
    layers = [_name(layer_by_id.get(lid), lid) for lid in _str_list(getattr(relation, "layer_ids", []))]
    lines = [
        _line("Kind", "Relation"),
        _line("Type", _enum_value(getattr(relation, "relation_type", ""))),
        _line("Source", _name(entity_by_id.get(source_id), source_id)),
        _line("Target", _name(entity_by_id.get(target_id), target_id)),
        _line("Description", getattr(relation, "description", "")),
        _line("Temporality", getattr(relation, "temporality", "")),
        _line("Causality", getattr(relation, "causality", "")),
        _line("Intensity", _enum_value(getattr(relation, "intensity", ""))),
        _line("Layers", ", ".join(layers)),
        _line("Tags", ", ".join(_str_list(getattr(relation, "tags", [])))),
    ]
    return _join_lines(lines)


def _render_world_layer(layer: Any, entity_by_id: dict[str, Any], relations: list[Any]) -> str:
    member_names = [
        _name(entity, str(getattr(entity, "id", "")))
        for entity in entity_by_id.values()
        if str(getattr(layer, "id", "")) in _str_list(getattr(entity, "layer_ids", []))
    ]
    metadata = getattr(layer, "metadata", {}) or {}
    lines = [
        _line("Kind", "World layer"),
        _line("Name", getattr(layer, "name", "")),
        _line("Description", getattr(layer, "description", "")),
        _line("Order", getattr(layer, "order", "")),
        _line("Causal role", metadata.get("causal_role", "")),
        _line("Causal aliases", metadata.get("causal_aliases", "")),
        _line("Members", ", ".join(member_names)),
        _line("Relation count", sum(1 for relation in relations if str(getattr(layer, "id", "")) in _str_list(getattr(relation, "layer_ids", [])))),
    ]
    return _join_lines(lines)


def _render_milestone(milestone: Any, entity_by_id: dict[str, Any], layer_by_id: dict[str, Any]) -> str:
    entity_names = [_name(entity_by_id.get(eid), eid) for eid in _str_list(getattr(milestone, "affected_entity_ids", []))]
    layer_names = [_name(layer_by_id.get(lid), lid) for lid in _str_list(getattr(milestone, "layer_ids", []))]
    temporality = getattr(milestone, "temporality", None)
    lines = [
        _line("Kind", "Milestone"),
        _line("Title", getattr(milestone, "title", "")),
        _line("Type", _enum_value(getattr(milestone, "milestone_type", ""))),
        _line("Status", _enum_value(getattr(milestone, "status", ""))),
        _line("Description", getattr(milestone, "description", "")),
        _line("Rationale", getattr(milestone, "rationale", "")),
        _line("Temporality", _compact_json(temporality.to_dict() if hasattr(temporality, "to_dict") else {})),
        _line("Affected entities", ", ".join(entity_names)),
        _line("Layers", ", ".join(layer_names)),
        _line("Tags", ", ".join(_str_list(getattr(milestone, "tags", [])))),
    ]
    return _join_lines(lines)


def _render_chronology(chronology: Any) -> str:
    lines = [
        _line("Kind", "Project chronology"),
        _line("Name", getattr(chronology, "calendar_name", "")),
        _line("Description", getattr(chronology, "description", "")),
        _line("System", getattr(chronology, "calendar_system", "")),
        _line("Milestones", ", ".join(_str_list(getattr(chronology, "milestone_ids", [])))),
        _line("Metadata", _compact_json(getattr(chronology, "metadata", {}) or {})),
    ]
    return _join_lines(lines)


def _render_candidate(candidate: Any) -> str:
    lines = [
        _line("Kind", "Candidate"),
        _line("Title", getattr(candidate, "title", "")),
        _line("Type", _enum_value(getattr(candidate, "candidate_type", ""))),
        _line("State", _enum_value(getattr(candidate, "state", ""))),
        _line("Justification", getattr(candidate, "justification", "")),
        _line("Expected impact", getattr(candidate, "expected_impact", "")),
        _line("Proposed data", _compact_json(getattr(candidate, "proposed_data", {}) or {})),
        _line("Possible contradictions", "; ".join(_str_list(getattr(candidate, "possible_contradictions", [])))),
    ]
    return _join_lines(lines)


def _render_issue(issue: Any) -> str:
    lines = [
        _line("Kind", "Issue"),
        _line("Type", _enum_value(getattr(issue, "type", getattr(issue, "issue_type", "")))),
        _line("Severity", _enum_value(getattr(issue, "severity", ""))),
        _line("State", _enum_value(getattr(issue, "state", ""))),
        _line("Description", getattr(issue, "description", "")),
        _line("Evidence", getattr(issue, "evidence", "")),
        _line("Possible solutions", "; ".join(_str_list(getattr(issue, "possible_solutions", [])))),
        _line("Resolution", getattr(issue, "resolution", "")),
    ]
    return _join_lines(lines)


def _creative_record(project: Any, indexed_at: str) -> CorpusIndexRecord | None:
    config = getattr(project, "creative_config", None)
    if config is None:
        return None
    data = config.to_dict() if hasattr(config, "to_dict") else {}
    if not _has_content(data) and not getattr(project, "description", ""):
        return None
    text = _join_lines([
        _line("Kind", "Creative config"),
        _line("Project", getattr(project, "name", "")),
        _line("Description", getattr(project, "description", "")),
        _line("Configuration", _compact_json(data)),
    ])
    return _make_record(
        kind=CorpusItemKind.CREATIVE_CONFIG,
        ref_id="creative_config",
        source="project.creative_config",
        rendered_text=text,
        references=[],
        metadata={"project_type": getattr(project, "project_type", ""), "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False))},
        updated_at=_string_value(getattr(project, "updated_at", "")),
        indexed_at=indexed_at,
    )


def _contains_maps(relations: list[Any]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    parent_map: dict[str, list[str]] = {}
    child_map: dict[str, list[str]] = {}
    for relation in relations:
        if _enum_value(getattr(relation, "relation_type", "")) != "contiene":
            continue
        source_id = str(getattr(relation, "source_id", ""))
        target_id = str(getattr(relation, "target_id", ""))
        if source_id and target_id:
            parent_map.setdefault(target_id, []).append(source_id)
            child_map.setdefault(source_id, []).append(target_id)
    return parent_map, child_map


def _is_branch_entity(entity: Any) -> bool:
    metadata = getattr(entity, "custom_metadata", {}) or {}
    display_type = str(metadata.get("display_type", "") or getattr(entity, "display_type", "")).lower()
    entity_type = _enum_value(getattr(entity, "entity_type", "")).lower()
    return display_type == "rama" or bool(metadata.get("candidate_tree")) or entity_type in BRANCH_ENTITY_TYPES


def _indexable_state(item: Any, audience: str) -> bool:
    if _enum_value(getattr(item, "canon_state", "")) in ARCHIVED_CANON_STATES:
        return False
    return _visibility_allowed(getattr(item, "visibility_state", ""), audience)


def _visibility_allowed(value: Any, audience: str) -> bool:
    if str(audience or "").lower() in {"gm", "author", "autor"}:
        return True
    return _enum_value(value) not in PRIVATE_VISIBILITY_STATES


def _candidate_included(candidate: Any, options: IndexingOptions) -> bool:
    state = _enum_value(getattr(candidate, "state", ""))
    if state in ACCEPTED_CANDIDATE_STATES:
        return options.include_accepted_candidates
    if state in PENDING_CANDIDATE_STATES:
        return options.include_pending_candidates
    if state in REJECTED_CANDIDATE_STATES:
        return options.include_rejected_candidates
    return False


def _chronology_has_content(chronology: Any) -> bool:
    return bool(
        getattr(chronology, "calendar_name", "")
        or getattr(chronology, "description", "")
        or getattr(chronology, "milestone_ids", [])
        or _has_content(getattr(chronology, "metadata", {}) or {})
    )


def _entity_references(entity: Any, parent_map: dict[str, list[str]]) -> list[str]:
    refs = [f"world_layer:{lid}" for lid in _str_list(getattr(entity, "layer_ids", []))]
    refs.extend(f"branch:{pid}" for pid in parent_map.get(str(getattr(entity, "id", "")), []))
    return refs


def _relation_references(relation: Any) -> list[str]:
    refs = [
        f"entity:{getattr(relation, 'source_id', '')}",
        f"entity:{getattr(relation, 'target_id', '')}",
    ]
    refs.extend(f"world_layer:{lid}" for lid in _str_list(getattr(relation, "layer_ids", [])))
    return refs


def _layer_references(layer: Any, entities: list[Any]) -> list[str]:
    layer_id = str(getattr(layer, "id", ""))
    return [f"entity:{getattr(entity, 'id', '')}" for entity in entities if layer_id in _str_list(getattr(entity, "layer_ids", []))]


def _milestone_references(milestone: Any) -> list[str]:
    refs: list[str] = []
    refs.extend(f"entity:{eid}" for eid in _str_list(getattr(milestone, "affected_entity_ids", [])))
    refs.extend(f"branch:{bid}" for bid in _str_list(getattr(milestone, "affected_branch_ids", [])))
    refs.extend(f"world_layer:{lid}" for lid in _str_list(getattr(milestone, "layer_ids", [])))
    refs.extend(f"world_layer:{lid}" for lid in _str_list(getattr(milestone, "affected_layer_ids", [])))
    refs.extend(f"relation:{rid}" for rid in _str_list(getattr(milestone, "caused_relation_ids", [])))
    refs.extend(f"milestone:{hid}" for hid in _str_list(getattr(milestone, "causal_parent_hito_ids", [])))
    refs.extend(f"milestone:{hid}" for hid in _str_list(getattr(milestone, "causal_child_hito_ids", [])))
    return refs


def _candidate_references(candidate: Any) -> list[str]:
    refs = [f"entity:{eid}" for eid in _str_list(getattr(candidate, "affected_entity_ids", []))]
    refs.extend(f"relation:{rid}" for rid in _str_list(getattr(candidate, "affected_relation_ids", [])))
    source_id = getattr(candidate, "source_id", None)
    if source_id:
        refs.append(f"source:{source_id}")
    return refs


def _issue_references(issue: Any) -> list[str]:
    refs = [f"entity:{eid}" for eid in _str_list(getattr(issue, "affected_entity_ids", []))]
    refs.extend(f"relation:{rid}" for rid in _str_list(getattr(issue, "affected_relation_ids", [])))
    refs.extend(f"source:{sid}" for sid in _str_list(getattr(issue, "affected_source_ids", [])))
    for attr, prefix in (("affected_entity_id", "entity"), ("affected_relation_id", "relation"), ("affected_source_id", "source")):
        value = getattr(issue, attr, None)
        if value:
            refs.append(f"{prefix}:{value}")
    return refs


def _entity_metadata(entity: Any, kind: CorpusItemKind, parent_map: dict[str, list[str]], child_map: dict[str, list[str]]) -> dict[str, Any]:
    metadata = getattr(entity, "custom_metadata", {}) or {}
    return {
        "display_kind": kind.value,
        "entity_type": _enum_value(getattr(entity, "entity_type", "")),
        "canon_state": _enum_value(getattr(entity, "canon_state", "")),
        "visibility_state": _enum_value(getattr(entity, "visibility_state", "")),
        "layer_ids": _str_list(getattr(entity, "layer_ids", [])),
        "tags": _str_list(getattr(entity, "tags", [])),
        "parent_branch_ids": list(parent_map.get(str(getattr(entity, "id", "")), [])),
        "child_entity_ids": list(child_map.get(str(getattr(entity, "id", "")), [])),
        "has_private_notes": bool(getattr(entity, "private_notes", "")),
        "tree_type": metadata.get("tree_type", ""),
        "tree_narrative_role": metadata.get("tree_narrative_role", ""),
    }


def _relation_metadata(relation: Any) -> dict[str, Any]:
    relation_type = _enum_value(getattr(relation, "relation_type", ""))
    return {
        "relation_type": relation_type,
        "source_id": getattr(relation, "source_id", ""),
        "target_id": getattr(relation, "target_id", ""),
        "canon_state": _enum_value(getattr(relation, "canon_state", "")),
        "visibility_state": _enum_value(getattr(relation, "visibility_state", "")),
        "layer_ids": _str_list(getattr(relation, "layer_ids", [])),
        "tags": _str_list(getattr(relation, "tags", [])),
        "structural": relation_type in {"contiene", "pertenece_a"},
    }


def _layer_metadata(layer: Any) -> dict[str, Any]:
    metadata = getattr(layer, "metadata", {}) or {}
    return {
        "order": getattr(layer, "order", 0),
        "is_default": bool(getattr(layer, "is_default", False)),
        "causal_rank": metadata.get("causal_rank", ""),
        "causal_role": metadata.get("causal_role", ""),
        "causal_parent_layer_ids": metadata.get("causal_parent_layer_ids", ""),
    }


def _milestone_metadata(milestone: Any) -> dict[str, Any]:
    return {
        "milestone_type": _enum_value(getattr(milestone, "milestone_type", "")),
        "status": _enum_value(getattr(milestone, "status", "")),
        "layer_ids": _str_list(getattr(milestone, "layer_ids", [])),
        "affected_entity_ids": _str_list(getattr(milestone, "affected_entity_ids", [])),
        "affected_branch_ids": _str_list(getattr(milestone, "affected_branch_ids", [])),
        "caused_relation_ids": _str_list(getattr(milestone, "caused_relation_ids", [])),
        "tags": _str_list(getattr(milestone, "tags", [])),
    }


def _candidate_metadata(candidate: Any) -> dict[str, Any]:
    return {
        "candidate_type": _enum_value(getattr(candidate, "candidate_type", "")),
        "state": _enum_value(getattr(candidate, "state", "")),
        "source": getattr(candidate, "source", ""),
        "source_id": getattr(candidate, "source_id", None),
        "confidence": getattr(candidate, "confidence", 0.0),
    }


def _issue_metadata(issue: Any) -> dict[str, Any]:
    return {
        "type": _enum_value(getattr(issue, "type", getattr(issue, "issue_type", ""))),
        "severity": _enum_value(getattr(issue, "severity", "")),
        "state": _enum_value(getattr(issue, "state", "")),
        "is_intentional": bool(getattr(issue, "is_intentional", False)),
    }


def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_nested(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _content_hash(
    kind: CorpusItemKind,
    ref_id: str,
    rendered_text: str,
    references: list[str],
    metadata: dict[str, Any],
) -> str:
    payload = {
        "kind": kind.value,
        "ref_id": ref_id,
        "rendered_text": rendered_text,
        "references": references,
        "metadata": metadata,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _estimate_tokens(text: str) -> int:
    words = re.findall(r"\w+", text or "", flags=re.UNICODE)
    if not words:
        return 0
    return max(1, int(len(words) * 1.35))


def _counts_by_kind(records: Iterable[CorpusIndexRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.kind.value] = counts.get(record.kind.value, 0) + 1
    return counts


def _compact_json(value: Any, *, limit: int = 1600) -> str:
    safe = sanitize_nested(value) if isinstance(value, dict) else value
    text = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def _line(label: str, value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return f"{label}: {text}" if text else ""


def _join_lines(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)


def _name(item: Any, fallback: str = "") -> str:
    if item is None:
        return fallback
    return str(getattr(item, "name", "") or getattr(item, "title", "") or fallback)


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "")


def _string_value(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _has_content(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    return bool(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CorpusIndexer",
    "CorpusIndexRecord",
    "CorpusIndexStats",
    "IndexingOptions",
    "NarrativeCorpusIndex",
]
