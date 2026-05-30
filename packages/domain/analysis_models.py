"""AI analysis domain models — Bloque 16.
stdlib-only, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CriticalAnalysisTarget(str, Enum):
    ENTITY = "entity"
    ENTITY_GROUP = "entity_group"
    ENTITY_RELATIONS = "entity_relations"
    PLOT = "plot"
    FACTION = "faction"
    LOCATION = "location"
    SCENE_SET = "scene_set"
    WORLD_LAYER = "world_layer"
    FULL_PROJECT = "full_project"


@dataclass
class CriticalAnalysisResult:
    target_id: str | None = None
    target_type: CriticalAnalysisTarget = CriticalAnalysisTarget.ENTITY
    observations: list[str] = field(default_factory=list)
    candidate_issues: list[dict[str, Any]] = field(default_factory=list)
    correction_proposals: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    underutilized_elements: list[str] = field(default_factory=list)
    redundant_elements: list[str] = field(default_factory=list)
    tone_risks: list[str] = field(default_factory=list)
    structure_risks: list[str] = field(default_factory=list)
    continuity_problems: list[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type.value,
            "observations": list(self.observations),
            "candidate_issues": list(self.candidate_issues),
            "correction_proposals": list(self.correction_proposals),
            "open_questions": list(self.open_questions),
            "underutilized_elements": list(self.underutilized_elements),
            "redundant_elements": list(self.redundant_elements),
            "tone_risks": list(self.tone_risks),
            "structure_risks": list(self.structure_risks),
            "continuity_problems": list(self.continuity_problems),
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriticalAnalysisResult:
        return cls(
            target_id=data.get("target_id"),
            target_type=_pe(CriticalAnalysisTarget, data.get("target_type"), CriticalAnalysisTarget.ENTITY),
            observations=_pl(data.get("observations")),
            candidate_issues=_pld(data.get("candidate_issues")),
            correction_proposals=_pld(data.get("correction_proposals")),
            open_questions=_pls(data.get("open_questions")),
            underutilized_elements=_pls(data.get("underutilized_elements")),
            redundant_elements=_pls(data.get("redundant_elements")),
            tone_risks=_pls(data.get("tone_risks")),
            structure_risks=_pls(data.get("structure_risks")),
            continuity_problems=_pls(data.get("continuity_problems")),
            raw_response=data.get("raw_response", ""),
        )


@dataclass
class CausalAnalysisResult:
    source_entity_id: str = ""
    direct_consequences: list[dict[str, Any]] = field(default_factory=list)
    indirect_consequences: list[dict[str, Any]] = field(default_factory=list)
    delayed_consequences: list[dict[str, Any]] = field(default_factory=list)
    events_without_cause: list[str] = field(default_factory=list)
    absent_consequences: list[str] = field(default_factory=list)
    causal_relation_candidates: list[dict[str, Any]] = field(default_factory=list)
    affected_entity_ids: list[str] = field(default_factory=list)
    severity_classification: dict[str, str] = field(default_factory=dict)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_entity_id": self.source_entity_id,
            "direct_consequences": list(self.direct_consequences),
            "indirect_consequences": list(self.indirect_consequences),
            "delayed_consequences": list(self.delayed_consequences),
            "events_without_cause": list(self.events_without_cause),
            "absent_consequences": list(self.absent_consequences),
            "causal_relation_candidates": list(self.causal_relation_candidates),
            "affected_entity_ids": list(self.affected_entity_ids),
            "severity_classification": dict(self.severity_classification),
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CausalAnalysisResult:
        return cls(
            source_entity_id=data.get("source_entity_id", ""),
            direct_consequences=_pld(data.get("direct_consequences")),
            indirect_consequences=_pld(data.get("indirect_consequences")),
            delayed_consequences=_pld(data.get("delayed_consequences")),
            events_without_cause=_pls(data.get("events_without_cause")),
            absent_consequences=_pls(data.get("absent_consequences")),
            causal_relation_candidates=_pld(data.get("causal_relation_candidates")),
            affected_entity_ids=_pls(data.get("affected_entity_ids")),
            severity_classification=_pd(data.get("severity_classification")),
            raw_response=data.get("raw_response", ""),
        )


@dataclass
class ConsistencyAnalysisResult:
    scope_id: str | None = None
    narrative_contradictions: list[dict[str, Any]] = field(default_factory=list)
    motivational_contradictions: list[dict[str, Any]] = field(default_factory=list)
    knowledge_contradictions: list[dict[str, Any]] = field(default_factory=list)
    tone_contradictions: list[dict[str, Any]] = field(default_factory=list)
    genre_contradictions: list[dict[str, Any]] = field(default_factory=list)
    scale_contradictions: list[dict[str, Any]] = field(default_factory=list)
    causal_gaps: list[dict[str, Any]] = field(default_factory=list)
    faction_incoherences: list[dict[str, Any]] = field(default_factory=list)
    inter_session_incoherences: list[dict[str, Any]] = field(default_factory=list)
    framework_content_incoherences: list[dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "narrative_contradictions": list(self.narrative_contradictions),
            "motivational_contradictions": list(self.motivational_contradictions),
            "knowledge_contradictions": list(self.knowledge_contradictions),
            "tone_contradictions": list(self.tone_contradictions),
            "genre_contradictions": list(self.genre_contradictions),
            "scale_contradictions": list(self.scale_contradictions),
            "causal_gaps": list(self.causal_gaps),
            "faction_incoherences": list(self.faction_incoherences),
            "inter_session_incoherences": list(self.inter_session_incoherences),
            "framework_content_incoherences": list(self.framework_content_incoherences),
            "raw_response": self.raw_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsistencyAnalysisResult:
        return cls(
            scope_id=data.get("scope_id"),
            narrative_contradictions=_pld(data.get("narrative_contradictions")),
            motivational_contradictions=_pld(data.get("motivational_contradictions")),
            knowledge_contradictions=_pld(data.get("knowledge_contradictions")),
            tone_contradictions=_pld(data.get("tone_contradictions")),
            genre_contradictions=_pld(data.get("genre_contradictions")),
            scale_contradictions=_pld(data.get("scale_contradictions")),
            causal_gaps=_pld(data.get("causal_gaps")),
            faction_incoherences=_pld(data.get("faction_incoherences")),
            inter_session_incoherences=_pld(data.get("inter_session_incoherences")),
            framework_content_incoherences=_pld(data.get("framework_content_incoherences")),
            raw_response=data.get("raw_response", ""),
        )


def _pe(ec, v, d):
    if isinstance(v, ec): return v
    if isinstance(v, str):
        try: return ec(v)
        except ValueError: pass
    return d

def _pl(v): return list(v) if isinstance(v, list) else []
def _pls(v): return [str(x) for x in v] if isinstance(v, list) else []
def _pd(v): return dict(v) if isinstance(v, dict) else {}
def _pld(v): return [dict(x) for x in v] if isinstance(v, list) else []


__all__ = ["CriticalAnalysisTarget", "CriticalAnalysisResult", "CausalAnalysisResult", "ConsistencyAnalysisResult"]
