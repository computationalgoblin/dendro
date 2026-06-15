"""Unit coverage for AnalysisService (DC-045)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from packages.application.orchestrator_service import OrchestratorService

from packages.application.analysis_service import AnalysisService
from packages.domain.ai_models import AIMode, AIOperation, AIResponse, AuthorizedContext
from packages.domain.analysis_models import (
    CausalAnalysisResult,
    ConsistencyAnalysisResult,
    CriticalAnalysisResult,
    CriticalAnalysisTarget,
)
from packages.domain.candidate_issue import StructuredIssue, StructuredIssueType
from packages.domain.result import Error, Ok


class FakeCandidateService:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create_candidate(self, data: dict):
        self.created.append(dict(data))
        return Ok(SimpleNamespace(id=f"cand-{len(self.created)}"))


class FakeOrchestrator:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[tuple] = []
        self._cs = FakeCandidateService()

    def invoke(self, mode, entity_id=None, prompt_hint="", filters=None):
        self.calls.append((mode, entity_id, prompt_hint, filters))
        return self.response


class FakeIssueService:
    def __init__(self) -> None:
        self.issues: list[StructuredIssue] = []

    def add_issue(self, issue: StructuredIssue) -> None:
        self.issues.append(issue)


class FakeSourceService:
    def __init__(self) -> None:
        self.sources: list[dict] = []

    def add_source(self, data: dict):
        self.sources.append(dict(data))
        return Ok(SimpleNamespace(id=f"src-{len(self.sources)}"))


def _response(mode: AIMode, *, candidates=None, observations=None, raw_text="raw") -> AIResponse:
    return AIResponse(
        id="resp-1",
        operation=AIOperation(
            mode=mode,
            context=AuthorizedContext(
                audience="author",
                allowed_canon_states=["canon"],
                allowed_visibility_states=["publico"],
            ),
        ),
        raw_text=raw_text,
        candidates=list(candidates or []),
        observations=list(observations or []),
        provider="fake-provider",
    )


def test_analyze_entity_propagates_orchestrator_errors() -> None:
    orch = FakeOrchestrator(Error("provider down"))
    service = AnalysisService(cast(OrchestratorService, orch))

    result = service.analyze_entity("ent-1", filters={"audience": "author"})

    assert isinstance(result, Error)
    assert result.error == "provider down"
    assert orch.calls == [(AIMode.CRITICAL_ANALYSIS, "ent-1", "", {"audience": "author"})]


def test_analyze_entity_splits_issues_and_correction_proposals_and_traces_source() -> None:
    resp = _response(
        AIMode.CRITICAL_ANALYSIS,
        observations=["El arco funciona"],
        candidates=[
            {"type": "contradiction", "description": "Motivación incompatible"},
            {"title": "Ajustar motivación", "proposed_data": {"field": "motivation"}},
        ],
        raw_text="detalle del análisis",
    )
    orch = FakeOrchestrator(Ok(resp))
    issues = FakeIssueService()
    sources = FakeSourceService()
    service = AnalysisService(cast(OrchestratorService, orch), issue_service=issues, source_service=sources)

    result = service.analyze_entity("ent-1")

    assert isinstance(result, Ok)
    value = result.value
    assert isinstance(value, CriticalAnalysisResult)
    assert value.target_id == "ent-1"
    assert value.target_type is CriticalAnalysisTarget.ENTITY
    assert value.observations == ["El arco funciona"]
    assert value.candidate_issues == [{"type": "contradiction", "description": "Motivación incompatible"}]
    assert value.correction_proposals == [
        {"title": "Ajustar motivación", "proposed_data": {"field": "motivation"}}
    ]
    assert len(sources.sources) == 1
    assert sources.sources[0]["metadata"]["provider"] == "fake-provider"
    assert len(issues.issues) == 1
    assert issues.issues[0].description == "Motivación incompatible"
    # Unknown StructuredIssueType values fall back safely instead of crashing.
    assert issues.issues[0].type is StructuredIssueType.INVALID_ENTITY_TYPE
    assert issues.issues[0].metadata == {"ai_mode": "critical", "source": "ia", "source_id": "src-1"}
    assert issues.issues[0].affected_source_ids == ["src-1"]
    assert orch._cs.created == [
        {
            "title": "Ajustar motivación",
            "candidate_type": "correccion",
            "proposed_data": {"title": "Ajustar motivación", "proposed_data": {"field": "motivation"}},
            "source": "ia",
            "source_id": "src-1",
            "confidence": 0.5,
        }
    ]


def test_analyze_causal_classifies_relation_and_entity_candidates() -> None:
    resp = _response(
        AIMode.CAUSAL_ANALYSIS,
        candidates=[
            {"source_id": "a", "target_id": "b", "relation_type": "causa"},
            {"name": "Consecuencia", "entity_type": "evento"},
        ],
    )
    orch = FakeOrchestrator(Ok(resp))
    service = AnalysisService(cast(OrchestratorService, orch), source_service=FakeSourceService())

    result = service.analyze_causal("ent-1")

    assert isinstance(result, Ok)
    value = result.value
    assert isinstance(value, CausalAnalysisResult)
    assert value.source_entity_id == "ent-1"
    assert value.causal_relation_candidates == [
        {"source_id": "a", "target_id": "b", "relation_type": "causa"}
    ]
    assert value.direct_consequences == [{"name": "Consecuencia", "entity_type": "evento"}]
    assert [c["candidate_type"] for c in orch._cs.created] == ["relacion", "entidad"]


def test_analyze_consistency_groups_causal_gaps_and_records_issues() -> None:
    resp = _response(
        AIMode.CONSISTENCY_ANALYSIS,
        candidates=[
            {"type": "narrative", "description": "Contradicción de tono"},
            {"type": "causal_gap", "description": "Falta causa"},
            {"description": "Sin tipo explícito"},
        ],
    )
    orch = FakeOrchestrator(Ok(resp))
    issues = FakeIssueService()
    service = AnalysisService(cast(OrchestratorService, orch), issue_service=issues, source_service=FakeSourceService())

    result = service.analyze_consistency(scope_id="scope-1")

    assert isinstance(result, Ok)
    value = result.value
    assert isinstance(value, ConsistencyAnalysisResult)
    assert value.scope_id == "scope-1"
    assert value.narrative_contradictions == [
        {"type": "narrative", "description": "Contradicción de tono"},
        {"description": "Sin tipo explícito"},
    ]
    assert value.causal_gaps == [{"type": "causal_gap", "description": "Falta causa"}]
    assert [issue.description for issue in issues.issues] == [
        "Contradicción de tono",
        "Falta causa",
        "Sin tipo explícito",
    ]
