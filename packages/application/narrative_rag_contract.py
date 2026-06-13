"""Advanced narrative RAG contract (E01).

This module defines pure application-layer DTOs for later RAG tickets. It does
not index, retrieve, call providers or mutate canon.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CorpusItemKind(str, Enum):
    ENTITY = "entity"
    BRANCH = "branch"
    RELATION = "relation"
    WORLD_LAYER = "world_layer"
    MILESTONE = "milestone"
    CHRONOLOGY = "chronology"
    CANDIDATE = "candidate"
    ISSUE = "issue"
    IMPORT_DOCUMENT = "import_document"
    CREATIVE_CONFIG = "creative_config"


class RetrievalStrategy(str, Enum):
    PRECISION = "precision"
    BALANCED = "balanced"
    BREADTH = "breadth"
    CAUSAL = "causal"
    CHRONOLOGICAL = "chronological"


class ContextPriority(str, Enum):
    REQUIRED = "required"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass(frozen=True)
class RetrievalPlan:
    """Intent-aware retrieval request produced inside the AI pipeline."""

    intent_type: str
    query: str
    selected_entity_ids: list[str] = field(default_factory=list)
    selected_relation_ids: list[str] = field(default_factory=list)
    active_layer_ids: list[str] = field(default_factory=list)
    include_kinds: list[CorpusItemKind] = field(default_factory=list)
    strategy: RetrievalStrategy = RetrievalStrategy.BALANCED
    token_budget: int = 2400
    timeout_ms: int = 1500
    include_pending_candidates: bool = False
    include_rejected_candidates: bool = False
    include_unaccepted_imports: bool = False
    audience: str = "gm"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "query": self.query,
            "selected_entity_ids": list(self.selected_entity_ids),
            "selected_relation_ids": list(self.selected_relation_ids),
            "active_layer_ids": list(self.active_layer_ids),
            "include_kinds": [kind.value for kind in self.include_kinds],
            "strategy": self.strategy.value,
            "token_budget": self.token_budget,
            "timeout_ms": self.timeout_ms,
            "include_pending_candidates": self.include_pending_candidates,
            "include_rejected_candidates": self.include_rejected_candidates,
            "include_unaccepted_imports": self.include_unaccepted_imports,
            "audience": self.audience,
        }


@dataclass(frozen=True)
class ContextItem:
    """One retrieved narrative context item."""

    kind: CorpusItemKind
    ref_id: str
    source: str
    score: float
    reason: str
    priority: ContextPriority
    tokens_estimated: int
    rendered_text: str
    references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "ref_id": self.ref_id,
            "source": self.source,
            "score": self.score,
            "reason": self.reason,
            "priority": self.priority.value,
            "tokens_estimated": self.tokens_estimated,
            "rendered_text": self.rendered_text,
            "references": list(self.references),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ContextPack:
    """Structured, budgeted context returned by narrative retrieval."""

    plan: RetrievalPlan
    items: list[ContextItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tokens_budget: int = 2400
    tokens_estimated: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        estimated = self.tokens_estimated or sum(max(0, item.tokens_estimated) for item in self.items)
        object.__setattr__(self, "tokens_estimated", estimated)
        object.__setattr__(self, "tokens_budget", self.tokens_budget or self.plan.token_budget)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "context_pack/v1",
            "plan": self.plan.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "warnings": list(self.warnings),
            "tokens_budget": self.tokens_budget,
            "tokens_estimated": self.tokens_estimated,
            "truncated": self.truncated,
        }


INDEXABLE_KINDS: tuple[CorpusItemKind, ...] = (
    CorpusItemKind.ENTITY,
    CorpusItemKind.BRANCH,
    CorpusItemKind.RELATION,
    CorpusItemKind.WORLD_LAYER,
    CorpusItemKind.MILESTONE,
    CorpusItemKind.CHRONOLOGY,
    CorpusItemKind.CANDIDATE,
    CorpusItemKind.ISSUE,
    CorpusItemKind.IMPORT_DOCUMENT,
    CorpusItemKind.CREATIVE_CONFIG,
)


__all__ = [
    "ContextItem",
    "ContextPack",
    "ContextPriority",
    "CorpusItemKind",
    "INDEXABLE_KINDS",
    "RetrievalPlan",
    "RetrievalStrategy",
]
