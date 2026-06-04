"""B35 — Coherence analysis, context building, and repair flow tests.

Validates:
1. NarrativeContextBuilder.build_for_graph_selection includes tree_membership.
2. AIContextActionService.run_selection_coherence_analysis with mock provider.
3. AIContextActionService.run_selection_coherence_repair with mock provider.
4. PATCH_JSON parsing applies only to allowed fields.
5. Error on empty selection.
6. Error when provider fails.
7. Smoke: Devian/Akshan/Hermandad coherence scenario.
"""

import json

from packages.application.ai_context_actions import AIContextActionService
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.relation_service import RelationService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


# ── Fakes & Mocks ──────────────────────────────────────────────────────


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class FakeCandidateService:
    """Minimal candidate service stub."""
    pass


class MockAIProvider(AIProvider):
    """Deterministic provider that returns coherence-like responses."""

    @property
    def provider_name(self):
        return "mock"

    def __init__(self, response: str = ""):
        self._response = response
        self.calls: list[tuple[str, str]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message))
        return (self._response, None)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_tree_project():
    """Create project with Devian/Akshan/Hermandad scenario."""
    project = Project(name="Devian/Akshan smoke")
    # Entities
    hermandad = NarrativeEntity(name="Hermandad del Acero", entity_type=EntityType.CONTENEDOR)
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE,
                            brief_description="Asesino fugitivo, exmiembro de la Hermandad")
    akshan = NarrativeEntity(name="Akshan", entity_type=EntityType.PERSONAJE,
                            brief_description="Líder de la Hermandad del Acero")
    project.entities.extend([hermandad, devian, akshan])
    # Relations
    # CONTIENE: tree contains members
    r_cont1 = NarrativeRelation(source_id=hermandad.id, target_id=devian.id,
                                relation_type=RelationType.CONTIENE)
    r_cont2 = NarrativeRelation(source_id=hermandad.id, target_id=akshan.id,
                                relation_type=RelationType.CONTIENE)
    # Narrative relations
    r_sirve = NarrativeRelation(source_id=devian.id, target_id=akshan.id,
                                relation_type=RelationType.SIRVE_A,
                                description="Servidumbre limpia y leal")
    r_traicion = NarrativeRelation(source_id=devian.id, target_id=hermandad.id,
                                   relation_type=RelationType.TRAICIONO,
                                   description="Traicionó a la Hermandad")
    project.relations.extend([r_cont1, r_cont2, r_sirve, r_traicion])
    return project, hermandad, devian, akshan, r_sirve, r_traicion


# ── Tests: Context Builder ────────────────────────────────────────────


class TestGraphSelectionContext:
    """build_for_graph_selection includes tree context."""

    def test_entity_in_tree_has_tree_membership(self):
        project, tree, devian, akshan, _, _ = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[devian.id],
            relation_ids=[],
        )
        entities = ctx.get("selection", {}).get("entities", [])
        assert len(entities) == 1
        membership = entities[0].get("tree_membership", {})
        parent_trees = membership.get("parent_trees", [])
        assert any("Hermandad" in t for t in parent_trees)

    def test_entity_in_tree_has_ancestors(self):
        project, tree, devian, akshan, _, _ = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[devian.id],
            relation_ids=[],
        )
        entities = ctx.get("selection", {}).get("entities", [])
        assert len(entities) == 1
        ancestors = entities[0].get("tree_membership", {}).get("ancestors", [])
        assert len(ancestors) >= 1
        assert any(tree.id == a.get("id") for a in ancestors)

    def test_context_includes_nearby_relations(self):
        project, tree, devian, akshan, r_sirve, _ = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[devian.id],
            relation_ids=[],
        )
        nearby_rels = ctx.get("nearby_context", {}).get("relations", [])
        nearby_ids = [r.get("id") for r in nearby_rels]
        # r_sirve connects devian→akshan, should appear as nearby
        assert r_sirve.id in nearby_ids or any(
            r.get("relation_type") == "sirve_a" for r in nearby_rels
        )

    def test_context_includes_project_creative_config(self):
        project, tree, devian, akshan, _, _ = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[devian.id],
            relation_ids=[],
        )
        proj = ctx.get("project")
        assert proj is not None
        assert "tone" in proj
        assert "genre" in proj
        assert "realism" in proj

    def test_relation_expands_entity_ids(self):
        """Selecting a relation auto-includes source and target entities."""
        project, tree, devian, akshan, r_sirve, _ = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[],
            relation_ids=[r_sirve.id],
        )
        entities = ctx.get("selection", {}).get("entities", [])
        entity_ids = [e.get("id") for e in entities]
        assert devian.id in entity_ids
        assert akshan.id in entity_ids


# ── Tests: Coherence Analysis ─────────────────────────────────────────


class TestCoherenceAnalysis:
    """run_selection_coherence_analysis with mock provider."""

    def test_analysis_returns_ok(self):
        project, tree, devian, akshan, r_sirve, r_traicion = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        mock = MockAIProvider(response="Veredicto: Parcialmente coherente.")
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_analysis(
            entity_ids=[devian.id, akshan.id],
            relation_ids=[r_sirve.id],
        )
        assert isinstance(result, Ok)
        assert "Parcialmente coherente" in result.value.raw_text

    def test_analysis_no_selection_returns_error(self):
        project = Project(name="empty")
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        mock = MockAIProvider()
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_analysis(
            entity_ids=[],
            relation_ids=[],
        )
        assert isinstance(result, Error)

    def test_analysis_provider_error_returns_error(self):
        project, tree, devian, akshan, r_sirve, _ = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()

        class FailProvider(MockAIProvider):
            def chat(self, system_prompt, user_message, timeout=None):
                return (None, "Connection timeout")

        svc = AIContextActionService(ps, cs, provider=FailProvider())
        result = svc.run_selection_coherence_analysis(
            entity_ids=[devian.id],
            relation_ids=[r_sirve.id],
        )
        assert isinstance(result, Error)

    def test_analysis_prompt_includes_tree_context(self):
        project, tree, devian, akshan, r_sirve, _ = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        mock = MockAIProvider(response="OK")
        svc = AIContextActionService(ps, cs, provider=mock)
        svc.run_selection_coherence_analysis(
            entity_ids=[devian.id],
            relation_ids=[r_sirve.id],
        )
        # Verify the user prompt includes tree membership
        assert len(mock.calls) == 1
        user_prompt = mock.calls[0][1]
        assert "Hermandad" in user_prompt


# ── Tests: Coherence Repair ───────────────────────────────────────────


class TestCoherenceRepair:
    """run_selection_coherence_repair with mock provider."""

    def test_repair_returns_patch_json(self):
        project, tree, devian, akshan, r_sirve, _ = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        patch = {
            "entities": [{"id": devian.id, "brief_description": "Asesino vigilado por la Hermandad"}],
            "relations": [{"id": r_sirve.id, "description": "Servidumbre bajo chantaje y vigilancia"}],
        }
        mock_response = (
            "Resumen: La servidumbre de Devian hacia Akshan debe reflejar desconfianza.\n"
            f"<PATCH_JSON>{json.dumps(patch)}</PATCH_JSON>"
        )
        mock = MockAIProvider(response=mock_response)
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_repair(
            entity_ids=[devian.id, akshan.id],
            relation_ids=[r_sirve.id],
            proposal="Convertir servidumbre en deuda peligrosa",
        )
        assert isinstance(result, Ok)
        assert "<PATCH_JSON>" in result.value.raw_text
        assert "chantaje" in result.value.raw_text

    def test_repair_no_selection_returns_error(self):
        project = Project(name="empty")
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        mock = MockAIProvider()
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_repair(
            entity_ids=[],
            relation_ids=[],
        )
        assert isinstance(result, Error)


# ── Tests: PATCH_JSON parsing ─────────────────────────────────────────


class TestPatchParsing:
    """PATCH_JSON regex extraction and field filtering."""

    def test_parse_valid_patch(self):
        from hosts.DesktopHostPySide.widgets.coherence_panel import _PATCH_RE, _ALLOWED_ENTITY_FIELDS
        patch = {"entities": [{"id": "abc", "brief_description": "new"}]}
        text = f"<PATCH_JSON>{json.dumps(patch)}</PATCH_JSON>"
        m = _PATCH_RE.search(text)
        assert m is not None
        data = json.loads(m.group(1))
        assert data["entities"][0]["brief_description"] == "new"

    def test_allowed_entity_fields_dont_include_id_only(self):
        from hosts.DesktopHostPySide.widgets.coherence_panel import _ALLOWED_ENTITY_FIELDS
        # These fields are safe to patch
        assert "brief_description" in _ALLOWED_ENTITY_FIELDS
        assert "extended_description" in _ALLOWED_ENTITY_FIELDS
        # These should NOT be allowed
        assert "id" not in _ALLOWED_ENTITY_FIELDS
        assert "entity_type" not in _ALLOWED_ENTITY_FIELDS
        assert "canon_state" not in _ALLOWED_ENTITY_FIELDS

    def test_allowed_relation_fields(self):
        from hosts.DesktopHostPySide.widgets.coherence_panel import _ALLOWED_RELATION_FIELDS
        assert "description" in _ALLOWED_RELATION_FIELDS
        assert "temporality" in _ALLOWED_RELATION_FIELDS
        assert "id" not in _ALLOWED_RELATION_FIELDS
        assert "source_id" not in _ALLOWED_RELATION_FIELDS


# ── Smoke: Devian/Akshan/Hermandad ────────────────────────────────────


class TestDevianAkshanSmoke:
    """End-to-end smoke: Devian/Akshan/Hermandad coherence scenario.

    The IA should detect that Devian's clean servidumbre towards Akshan
    contradicts his betrayal of the Hermandad. The context must include
    tree membership showing both are in the Hermandad.
    """

    def test_context_shows_both_in_hermandad(self):
        project, tree, devian, akshan, r_sirve, r_traicion = _make_tree_project()
        ps = FakeProjectService(project)
        builder = NarrativeContextBuilder(ps)
        ctx = builder.build_for_graph_selection(
            entity_ids=[devian.id, akshan.id],
            relation_ids=[r_sirve.id, r_traicion.id],
        )
        entities = ctx["selection"]["entities"]
        for e in entities:
            if e["name"] == "Devian":
                parents = e["tree_membership"]["parent_trees"]
                assert any("Hermandad" in p for p in parents)
            if e["name"] == "Akshan":
                parents = e["tree_membership"]["parent_trees"]
                assert any("Hermandad" in p for p in parents)

    def test_coherence_analysis_receives_full_context(self):
        project, tree, devian, akshan, r_sirve, r_traicion = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        mock = MockAIProvider(response="Veredicto: Incoherente.")
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_analysis(
            entity_ids=[devian.id, akshan.id],
            relation_ids=[r_sirve.id, r_traicion.id],
        )
        assert isinstance(result, Ok)
        # Check the prompt includes both relations
        user_prompt = mock.calls[0][1]
        assert "sirve_a" in user_prompt or "servidumbre" in user_prompt.lower()
        assert "traiciono" in user_prompt or "traicion" in user_prompt.lower()

    def test_repair_generates_patch_for_sirve_a(self):
        project, tree, devian, akshan, r_sirve, r_traicion = _make_tree_project()
        ps = FakeProjectService(project)
        cs = FakeCandidateService()
        patch = {
            "relations": [{"id": r_sirve.id, "description": "Devian sirve a Akshan bajo amenaza de muerte"}],
        }
        mock = MockAIProvider(
            response="Resumen: La servidumbre debe reflejar coerción.\n"
                     f"<PATCH_JSON>{json.dumps(patch)}</PATCH_JSON>"
        )
        svc = AIContextActionService(ps, cs, provider=mock)
        result = svc.run_selection_coherence_repair(
            entity_ids=[devian.id, akshan.id],
            relation_ids=[r_sirve.id],
            proposal="Convertir en chantaje",
        )
        assert isinstance(result, Ok)
        assert "coerción" in result.value.raw_text or "PATCH_JSON" in result.value.raw_text
