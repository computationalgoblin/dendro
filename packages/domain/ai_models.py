"""AI orchestration domain models — Bloque 15.
stdlib-only, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AIMode(str, Enum):
    GENERATE_ENTITY = "generate_entity"
    GENERATE_RELATION = "generate_relation"
    EXPAND_ENTITY = "expand_entity"
    SUMMARIZE = "summarize"
    REWRITE_DESCRIPTION = "rewrite_description"
    SUGGEST_TAGS = "suggest_tags"
    SUGGEST_RELATIONS = "suggest_relations"
    CONTINUITY_QUESTION = "continuity_question"
    CRITICAL_ANALYSIS = "critical_analysis"
    CAUSAL_ANALYSIS = "causal_analysis"
    CONSISTENCY_ANALYSIS = "consistency_analysis"


@dataclass
class AuthorizedContext:
    project_name: str = ""
    domain_id: str | None = None
    layer_id: str | None = None
    selected_entity_ids: list[str] = field(default_factory=list)
    selected_relation_ids: list[str] = field(default_factory=list)
    allowed_canon_states: list[str] = field(default_factory=list)
    allowed_visibility_states: list[str] = field(default_factory=list)
    allowed_source_types: list[str] = field(default_factory=list)
    active_framework_ids: list[str] = field(default_factory=list)
    include_history: bool = False
    include_issues: bool = False
    output_profile: str = "default"
    audience: str = "author"
    project_config_snapshot: dict[str, Any] = field(default_factory=dict)
    framework_context: list[dict[str, Any]] = field(default_factory=list)
    context_entities: list[dict[str, Any]] = field(default_factory=list)
    context_relations: list[dict[str, Any]] = field(default_factory=list)
    context_history: list[dict[str, Any]] = field(default_factory=list)
    context_issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "domain_id": self.domain_id,
            "layer_id": self.layer_id,
            "selected_entity_ids": list(self.selected_entity_ids),
            "selected_relation_ids": list(self.selected_relation_ids),
            "allowed_canon_states": list(self.allowed_canon_states),
            "allowed_visibility_states": list(self.allowed_visibility_states),
            "allowed_source_types": list(self.allowed_source_types),
            "active_framework_ids": list(self.active_framework_ids),
            "include_history": self.include_history,
            "include_issues": self.include_issues,
            "output_profile": self.output_profile,
            "audience": self.audience,
            "project_config_snapshot": dict(self.project_config_snapshot),
            "framework_context": list(self.framework_context),
            "context_entities": list(self.context_entities),
            "context_relations": list(self.context_relations),
            "context_history": list(self.context_history),
            "context_issues": list(self.context_issues),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthorizedContext:
        return cls(
            project_name=data.get("project_name", ""),
            domain_id=data.get("domain_id"),
            layer_id=data.get("layer_id"),
            selected_entity_ids=_pl(data.get("selected_entity_ids")),
            selected_relation_ids=_pl(data.get("selected_relation_ids")),
            allowed_canon_states=_pl(data.get("allowed_canon_states")),
            allowed_visibility_states=_pl(data.get("allowed_visibility_states")),
            allowed_source_types=_pl(data.get("allowed_source_types")),
            active_framework_ids=_pl(data.get("active_framework_ids")),
            include_history=bool(data.get("include_history", False)),
            include_issues=bool(data.get("include_issues", False)),
            output_profile=data.get("output_profile", "default"),
            audience=data.get("audience", "author"),
            project_config_snapshot=_pd(data.get("project_config_snapshot")),
            framework_context=_pld(data.get("framework_context")),
            context_entities=_pld(data.get("context_entities")),
            context_relations=_pld(data.get("context_relations")),
            context_history=_pld(data.get("context_history")),
            context_issues=_pld(data.get("context_issues")),
        )


def _pl(v): return list(v) if isinstance(v, list) else []
def _pd(v): return dict(v) if isinstance(v, dict) else {}
def _pld(v): return [dict(x) for x in v] if isinstance(v, list) else []


@dataclass
class AIOperation:
    mode: AIMode = AIMode.GENERATE_ENTITY
    context: AuthorizedContext = field(default_factory=AuthorizedContext)
    prompt_hint: str = ""
    entity_id: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    max_candidates: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "context": self.context.to_dict(),
            "prompt_hint": self.prompt_hint,
            "entity_id": self.entity_id,
            "entity_ids": list(self.entity_ids),
            "max_candidates": self.max_candidates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AIOperation:
        return cls(
            mode=_pe(AIMode, data.get("mode"), AIMode.GENERATE_ENTITY),
            context=AuthorizedContext.from_dict(data.get("context", {})),
            prompt_hint=data.get("prompt_hint", ""),
            entity_id=data.get("entity_id"),
            entity_ids=_pl(data.get("entity_ids")),
            max_candidates=int(data.get("max_candidates", 3)),
        )


def _pe(ec, v, d):
    if isinstance(v, ec): return v
    if isinstance(v, str):
        try: return ec(v)
        except ValueError: pass
    return d


@dataclass
class AIResponse:
    id: str
    operation: AIOperation
    raw_text: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    error: str | None = None
    provider: str = "simulated"
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation.to_dict(),
            "raw_text": self.raw_text,
            "candidates": list(self.candidates),
            "observations": list(self.observations),
            "error": self.error,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AIResponse:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            operation=AIOperation.from_dict(data.get("operation", {})),
            raw_text=data.get("raw_text", ""),
            candidates=_pl(data.get("candidates")),
            observations=_pl(data.get("observations")),
            error=data.get("error"),
            provider=data.get("provider", "simulated"),
            latency_ms=float(data.get("latency_ms", 0.0)),
        )


__all__ = ["AIMode", "AuthorizedContext", "AIOperation", "AIResponse"]
