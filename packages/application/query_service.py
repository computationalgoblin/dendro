"""
Query service — unified read-only query layer.

Provides ``QueryService``, a fachada that aggregates queries across
entities, relations, sources, history, issues, and candidates.
All methods are read-only (§6.5 #6) — no mutation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from packages.domain.candidate_issue import Candidate, CandidateState, Issue, IssueState
from packages.domain.entity import (
    CanonState,
    CertaintyLevel,
    EntityType,
    NarrativeEntity,
    NarrativeImportance,
    VisibilityState,
)
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import HistoryEntry


# ═══════════════════════════════════════════════════════════════════════
# Result types (application-layer dataclasses, not domain)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class EntityCard:
    """Aggregated view of an entity for display/export.

    Contains the entity itself plus its neighbourhood of relations,
    recent history, linked sources, and open issues.
    """

    entity: NarrativeEntity
    incoming_relations: list[NarrativeRelation] = field(default_factory=list)
    outgoing_relations: list[NarrativeRelation] = field(default_factory=list)
    history: list[HistoryEntry] = field(default_factory=list)
    sources: list[Any] = field(default_factory=list)  # Source objects
    open_issues: list[Issue] = field(default_factory=list)


@dataclass
class GraphNeighborhood:
    """First-hop neighbourhood of an entity for graph views."""

    center: NarrativeEntity
    neighbors: list[NarrativeEntity] = field(default_factory=list)
    relations: list[NarrativeRelation] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


# ═══════════════════════════════════════════════════════════════════════
# QueryService
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class QueryService:
    """Unified read-only query layer over the narrative corpus.

    Wraps existing services and adds filters from §6.2 that are
    not already provided by EntityService or RelationService.

    Issues and candidates are read directly from the active project's
    collections — no separate service is required for read access.
    """

    entity_service: Any  # EntityService
    relation_service: Any  # RelationService
    source_service: Any  # SourceService
    history_service: Any | None = None  # HistoryService

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        es = self.entity_service
        if es.project_service.active_project is None:
            return Error("No active project")
        return Ok(es.project_service.active_project)

    def _all_entities(self) -> Result[list[NarrativeEntity], str]:
        return self.entity_service.list_all()

    def _all_relations(self) -> Result[list[NarrativeRelation], str]:
        return self.relation_service.list_all()

    # ------------------------------------------------------------------
    # New §6.2 filters
    # ------------------------------------------------------------------

    def filter_entities_by_source(
        self, source_id: str
    ) -> Result[list[NarrativeEntity], str]:
        """Entities derived from a source — §6.2 #10."""
        return self.source_service.get_entities_from_source(source_id)

    def filter_relations_by_source(
        self, source_id: str
    ) -> Result[list[NarrativeRelation], str]:
        """Relations derived from a source — §6.2 #10."""
        return self.source_service.get_sources_for_relation(source_id)

    def filter_by_modified_since(
        self, since: datetime
    ) -> Result[list[NarrativeEntity], str]:
        """Entities modified on or after *since* — §6.2 #11."""
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)
        return Ok([e for e in entities.value if e.updated_at >= since])

    def filter_by_modified_before(
        self, before: datetime
    ) -> Result[list[NarrativeEntity], str]:
        """Entities modified before *before* — §6.2 #11."""
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)
        return Ok([e for e in entities.value if e.updated_at < before])

    def filter_by_importance(
        self, level: NarrativeImportance
    ) -> Result[list[NarrativeEntity], str]:
        """Entities with a given narrative importance — §6.2 #12."""
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)
        return Ok([e for e in entities.value if e.narrative_importance == level])

    def filter_by_certainty(
        self, level: CertaintyLevel
    ) -> Result[list[NarrativeEntity], str]:
        """Entities with a given certainty level — §6.2 #13."""
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)
        return Ok([e for e in entities.value if e.certainty_level == level])

    def get_orphan_entities(
        self,
    ) -> Result[list[NarrativeEntity], str]:
        """Entities with no incoming or outgoing relations — §6.2 #18."""
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)
        relations = self._all_relations()
        if isinstance(relations, Error):
            return Error(relations.error)

        referenced_ids: set[str] = set()
        for r in relations.value:
            referenced_ids.add(r.source_id)
            referenced_ids.add(r.target_id)

        return Ok([e for e in entities.value if e.id not in referenced_ids])

    def get_pending_candidates(self) -> Result[list[Candidate], str]:
        """Candidates with state PENDIENTE — §6.2 #20."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([c for c in proj.value.candidates if c.state == CandidateState.PENDIENTE])

    def get_open_issues(self) -> Result[list[Issue], str]:
        """Issues with state ABIERTA or EN_PROGRESO."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([
            i for i in proj.value.issues
            if i.state in (IssueState.ABIERTA, IssueState.EN_PROGRESO)
        ])

    # ------------------------------------------------------------------
    # Combined queries
    # ------------------------------------------------------------------

    def query(
        self,
        entity_type=None,
        canon_state=None,
        visibility_state=None,
        tag: str | None = None,
        domain: str | None = None,
        layer: str | None = None,
        importance=None,
        custom_type_id: str | None = None,
        source_id: str | None = None,
        domain_id: str | None = None,
        layer_id: str | None = None,
        sort_by: str = "name",
        sort_desc: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[list[NarrativeEntity], str]:
        """Combine multiple filters on entities.

        Each filter is applied only when its argument is not None.
        Results are sorted and truncated to *limit*.

        *canon_state* accepts a single value, a list (OR semantics), or None.
        *custom_type_id* filters by ``entity.custom_type_id``.
        *source_id* filters entities linked to a specific source.
        *domain_id* filters by ``entity.domain_ids`` (new, §10).
        *layer_id* filters by ``entity.layer_ids`` (new, §10).
        *sort_by* accepts: name, updated_at, created_at, entity_type,
          canon_state, certainty, importance.
        *sort_desc* reverses sort direction when True.
        *offset* skips the first N results (pagination).
        """
        entities = self._all_entities()
        if isinstance(entities, Error):
            return Error(entities.error)

        results = list(entities.value)

        if entity_type is not None:
            if isinstance(entity_type, str):
                entity_type = EntityType(entity_type)
            results = [e for e in results if e.entity_type == entity_type]

        if canon_state is not None:
            if isinstance(canon_state, list):
                # OR semantics: match any of the listed states
                results = [e for e in results if e.canon_state in canon_state]
            else:
                if isinstance(canon_state, str):
                    canon_state = CanonState(canon_state)
                results = [e for e in results if e.canon_state == canon_state]

        if visibility_state is not None:
            if isinstance(visibility_state, str):
                visibility_state = VisibilityState(visibility_state)
            results = [e for e in results if e.visibility_state == visibility_state]

        if tag is not None:
            results = [e for e in results if tag in e.tags]

        if domain is not None:
            results = [e for e in results if e.domain == domain]

        if layer is not None:
            results = [e for e in results if layer in e.layers]

        if importance is not None:
            if isinstance(importance, str):
                importance = NarrativeImportance(importance)
            results = [e for e in results if e.narrative_importance == importance]

        if custom_type_id is not None:
            results = [e for e in results if e.custom_type_id == custom_type_id]

        if source_id is not None:
            source_entities = self.source_service.get_entities_from_source(source_id)
            if isinstance(source_entities, Error):
                return Error(source_entities.error)
            linked_ids = {e.id for e in source_entities.value}
            results = [e for e in results if e.id in linked_ids]

        if domain_id is not None:
            results = [e for e in results if domain_id in e.domain_ids]

        if layer_id is not None:
            results = [e for e in results if layer_id in e.layer_ids]

        if sort_by == "name":
            results.sort(key=lambda e: e.name.lower(), reverse=sort_desc)
        elif sort_by == "updated_at":
            results.sort(key=lambda e: e.updated_at, reverse=not sort_desc)
        elif sort_by == "created_at":
            results.sort(key=lambda e: e.created_at, reverse=sort_desc)
        elif sort_by == "entity_type":
            results.sort(key=lambda e: e.entity_type.value, reverse=sort_desc)
        elif sort_by == "canon_state":
            results.sort(key=lambda e: e.canon_state.value, reverse=sort_desc)
        elif sort_by == "certainty":
            results.sort(key=lambda e: e.certainty_level.value, reverse=sort_desc)
        elif sort_by == "importance":
            results.sort(key=lambda e: e.narrative_importance.value, reverse=sort_desc)
        else:
            return Error(f"Invalid sort field '{sort_by}'")

        return Ok(results[offset:offset + limit])

    # ------------------------------------------------------------------
    # Entity card (§6.5 #3)
    # ------------------------------------------------------------------

    def get_entity_card(self, entity_id: str) -> Result[EntityCard, str]:
        """Build an aggregated EntityCard for the given entity."""
        entity_result = self.entity_service.get_by_id(entity_id)
        if isinstance(entity_result, Error):
            return Error(entity_result.error)

        entity = entity_result.value

        incoming = self.relation_service.get_incoming(entity_id)
        outgoing = self.relation_service.get_outgoing(entity_id)

        history: list[HistoryEntry] = []
        if self.history_service is not None:
            hist = self.history_service.get_for_entity(entity_id)
            if isinstance(hist, Ok):
                history = hist.value[-10:]  # last 10

        sources_result = self.source_service.get_sources_for_entity(entity_id)
        sources = sources_result.value if isinstance(sources_result, Ok) else []

        issues_result = self.get_open_issues()
        all_issues = issues_result.value if isinstance(issues_result, Ok) else []
        open_issues = [i for i in all_issues if i.affected_entity_id == entity_id]

        return Ok(EntityCard(
            entity=entity,
            incoming_relations=incoming.value if isinstance(incoming, Ok) else [],
            outgoing_relations=outgoing.value if isinstance(outgoing, Ok) else [],
            history=history,
            sources=sources,
            open_issues=open_issues,
        ))

    # ------------------------------------------------------------------
    # Graph neighbourhood (§6.5 #4)
    # ------------------------------------------------------------------

    def build_graph_neighborhood(
        self, entity_id: str, depth: int = 1
    ) -> Result[GraphNeighborhood, str]:
        """Build a first-hop neighbourhood of an entity."""
        entity_result = self.entity_service.get_by_id(entity_id)
        if isinstance(entity_result, Error):
            return Error(entity_result.error)

        center = entity_result.value

        hood = self.relation_service.get_neighborhood(entity_id)
        if isinstance(hood, Error):
            return Error(hood.error)

        relations = hood.value

        neighbor_ids: set[str] = set()
        for r in relations:
            if r.source_id != entity_id:
                neighbor_ids.add(r.source_id)
            if r.target_id != entity_id:
                neighbor_ids.add(r.target_id)

        neighbors: list[NarrativeEntity] = []
        for nid in neighbor_ids:
            n = self.entity_service.get_by_id(nid)
            if isinstance(n, Ok):
                neighbors.append(n.value)

        return Ok(GraphNeighborhood(
            center=center,
            neighbors=neighbors,
            relations=relations,
            node_count=1 + len(neighbors),
            edge_count=len(relations),
        ))


__all__ = ["QueryService", "EntityCard", "GraphNeighborhood"]
