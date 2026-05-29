"""
Text search service — textual search across entities and relations.

Provides ``TextSearchService`` for case-insensitive contains search
over multiple text fields.  Includes privacy-aware ``include_private``
control and field-level whitelist for ``search_by_field``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.domain.entity import NarrativeEntity
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Error, Ok, Result


# Whitelist of allowed fields for search_by_field
_ALLOWED_ENTITY_FIELDS = frozenset({
    "name", "aliases", "brief_description", "extended_description",
    "private_notes", "exportable_notes", "tags", "domain", "layers",
    "origin",
})


@dataclass
class SearchResults:
    """Combined search results from ``search_all``."""

    entities: list[NarrativeEntity] = field(default_factory=list)
    relations: list[NarrativeRelation] = field(default_factory=list)

    @property
    def total_hits(self) -> int:
        return len(self.entities) + len(self.relations)


@dataclass
class TextSearchService:
    """Textual search over the narrative corpus (§6.3).

    All searches are case-insensitive contains matches.
    Results are ordered by relevance: exact name matches first,
    matches in description/notes later.
    """

    entity_service: Any  # EntityService
    relation_service: Any  # RelationService

    # ------------------------------------------------------------------
    # Entity search
    # ------------------------------------------------------------------

    def search_entities(
        self, query: str, include_private: bool = True,
    ) -> Result[list[NarrativeEntity], str]:
        """Search entities across name, aliases, descriptions, notes, tags.

        Args:
            query: Search term (case-insensitive contains).
            include_private: If True, search private_notes too.
                Set to False for public/export views.
        """
        entities = self.entity_service.list_all()
        if isinstance(entities, Error):
            return Error(entities.error)

        q = query.lower()
        results: list[tuple[NarrativeEntity, int]] = []  # (entity, score)

        for e in entities.value:
            score = self._entity_score(e, q, include_private)
            if score >= 0:
                results.append((e, score))

        # Sort by score descending (higher = better match)
        results.sort(key=lambda x: x[1], reverse=True)
        return Ok([e for e, _ in results])

    def search_by_field(
        self, query: str, field: str,
    ) -> Result[list[NarrativeEntity], str]:
        """Search entities in a single field.

        Args:
            query: Search term.
            field: Field name (must be in the whitelist).

        Returns:
            Error if the field is not allowed.
        """
        if field not in _ALLOWED_ENTITY_FIELDS:
            return Error(f"Unsupported search field: '{field}'")

        entities = self.entity_service.list_all()
        if isinstance(entities, Error):
            return Error(entities.error)

        q = query.lower()
        result: list[NarrativeEntity] = []

        for e in entities.value:
            value = self._get_field_value(e, field)
            if self._matches(value, q):
                result.append(e)

        return Ok(result)

    # ------------------------------------------------------------------
    # Relation search
    # ------------------------------------------------------------------

    def search_relations(
        self, query: str,
    ) -> Result[list[NarrativeRelation], str]:
        """Search relations across description, validity_conditions,
        temporality, causality, source, and tags."""
        relations = self.relation_service.list_all()
        if isinstance(relations, Error):
            return Error(relations.error)

        q = query.lower()
        result: list[NarrativeRelation] = []

        for r in relations.value:
            if self._relation_matches(r, q):
                result.append(r)

        return Ok(result)

    # ------------------------------------------------------------------
    # Combined
    # ------------------------------------------------------------------

    def search_all(
        self, query: str, include_private: bool = True,
    ) -> Result[SearchResults, str]:
        """Search both entities and relations."""
        entities = self.search_entities(query, include_private=include_private)
        relations = self.search_relations(query)

        return Ok(SearchResults(
            entities=entities.value if isinstance(entities, Ok) else [],
            relations=relations.value if isinstance(relations, Ok) else [],
        ))

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entity_score(
        entity: NarrativeEntity, q: str, include_private: bool,
    ) -> int:
        """Return a relevance score (higher = better).  -1 = no match."""
        # Exact name match = highest score
        if entity.name.lower() == q:
            return 100
        if q in entity.name.lower():
            return 80

        # Aliases
        for alias in entity.aliases:
            if q in alias.lower():
                return 60

        # Tags
        for tag in entity.tags:
            if q in tag.lower():
                return 40

        # Descriptions
        if q in entity.brief_description.lower():
            return 30
        if q in entity.extended_description.lower():
            return 20

        # Domain / layers / origin
        if q in entity.domain.lower():
            return 15
        for layer in entity.layers:
            if q in layer.lower():
                return 15
        if q in entity.origin.lower():
            return 10

        # Notes
        if q in entity.exportable_notes.lower():
            return 10
        if include_private and q in entity.private_notes.lower():
            return 5

        return -1

    @staticmethod
    def _relation_matches(relation: NarrativeRelation, q: str) -> bool:
        fields = [
            relation.description,
            *relation.validity_conditions,
            relation.temporality,
            relation.causality,
            relation.source,
        ]
        for tag in relation.tags:
            fields.append(tag)
        return any(q in str(f).lower() for f in fields if f)

    @staticmethod
    def _get_field_value(entity: NarrativeEntity, field: str):
        if field == "aliases":
            return entity.aliases
        if field == "tags":
            return entity.tags
        if field == "layers":
            return entity.layers
        return getattr(entity, field, "")

    @staticmethod
    def _matches(value: Any, q: str) -> bool:
        if isinstance(value, str):
            return q in value.lower()
        if isinstance(value, list):
            return any(q in str(v).lower() for v in value)
        return False


__all__ = ["TextSearchService", "SearchResults"]
