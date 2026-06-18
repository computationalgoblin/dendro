"""Tests for OrchestratorService (B15.8-T02 — DC-024).

BETA1-AI02: modes are plain strings now (AIMode removed); invoke() returns an
OrchestratorResult instead of an AIResponse.
"""
from packages.application.orchestrator_service import OrchestratorService
from packages.application.project_service import ProjectService
from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.domain.entity import EntityType
from packages.domain.result import Error
from packages.persistence.store import ProjectStore


_ALL_MODES = [
    "generate_entity", "generate_relation", "expand_entity", "summarize",
    "rewrite_description", "suggest_tags", "suggest_relations",
    "continuity_question", "critical_analysis", "causal_analysis",
    "consistency_analysis",
]


def _setup():
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    es = EntityService(project_service=ps)
    cs = CandidateService(ps, es)
    orch = OrchestratorService(ps, cs)
    return ps, orch, es


class TestOrchestratorBuildContext:
    def test_build_context_basic(self):
        ps, orch, es = _setup()
        es.create_entity({"name": "E", "entity_type": "personaje"})
        ctx = orch.build_context().value
        assert ctx.project_name == "Test"
        assert len(ctx.context_entities) == 1
        assert ctx.context_entities[0]["name"] == "E"

    def test_build_context_audience_player(self):
        ps, orch, es = _setup()
        es.create_entity({"name": "E", "entity_type": "personaje", "extended_description": "secret"})
        ctx = orch.build_context(filters={"audience": "player"}).value
        assert "extended_description" not in ctx.context_entities[0]


class TestOrchestratorInvoke:
    def test_invoke_simulated(self):
        ps, orch, _ = _setup()
        resp = orch.invoke("generate_entity").value
        assert resp.provider == "simulated"
        assert len(resp.candidates) == 2

    def test_all_modes(self):
        ps, orch, _ = _setup()
        for mode in _ALL_MODES:
            resp = orch.invoke(mode).value
            assert resp.provider == "simulated"
            assert resp.error is None


class TestOrchestratorGenerate:
    def test_generate_candidates(self):
        ps, orch, _ = _setup()
        cands = orch.generate_candidates("generate_entity").value
        assert len(cands) == 2
        assert all(c.source == "ia" for c in cands)

    def test_generate_no_mutation(self):
        ps, orch, _ = _setup()
        before = len(ps.active_project.entities)
        orch.generate_candidates("generate_entity")
        after = len(ps.active_project.entities)
        assert before == after

    def test_provider_error_handling(self):
        ps, orch, _ = _setup()
        orch._provider = None  # force error
        result = orch.invoke("generate_entity")
        assert isinstance(result, Error) or result.value.error is not None

    def test_all_modes_generate(self):
        ps, orch, _ = _setup()
        for mode in _ALL_MODES:
            result = orch.generate_candidates(mode)
            # some modes may return text-only, not candidates
            if not isinstance(result, Error):
                for c in result.value:
                    assert c.source == "ia"
