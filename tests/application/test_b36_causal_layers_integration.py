from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.application.ai_context_actions import AIContextActionService
from packages.application.candidate_service import CandidateService
from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.application.relation_service import RelationService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Ok
from packages.domain.world_layer import default_world_layers


class ProjectServiceStub:
    def __init__(self, project: Project):
        self.active_project = project


def _project() -> Project:
    now = datetime.now(timezone.utc)
    project = Project(id="proj_b36_integration", name="B36 integración", created_at=now, updated_at=now, worldbuilding_active=True)
    project.world_layers = default_world_layers()
    return project


def _entity(entity_id: str, name: str, layer_id: str, entity_type: EntityType = EntityType.NOTA) -> NarrativeEntity:
    return NarrativeEntity(
        id=entity_id,
        name=name,
        entity_type=entity_type,
        brief_description=name,
        layer_ids=[layer_id],
    )


@pytest.mark.application
def test_b36_relation_types_include_causal_mvp_values() -> None:
    assert RelationType.DERIVA_DE.value == "deriva_de"
    assert RelationType.CONDICIONA.value == "condiciona"
    assert RelationType.EXPLICA.value == "explica"
    assert RelationType.CONTRADICE.value == "contradice"
    assert RelationType.PRODUCE_CONSECUENCIA_EN.value == "produce_consecuencia_en"


@pytest.mark.application
def test_relation_service_persists_causal_type_and_layer_ids() -> None:
    project = _project()
    source = _entity("metafisica", "Dioses agujero negro", "layer_metafisica")
    target = _entity("fisica", "Gravedad inestable", "layer_fisica")
    project.entities.extend([source, target])
    service = RelationService(ProjectServiceStub(project))

    created = service.create_relation(data={
        "source_id": source.id,
        "target_id": target.id,
        "relation_type": "produce_consecuencia_en",
        "description": "La guerra divina altera la gravedad.",
        "causality": "Causa superior → consecuencia material",
        "layer_ids": ["layer_metafisica", "layer_fisica"],
    })

    assert isinstance(created, Ok)
    relation = created.value
    assert relation.relation_type is RelationType.PRODUCE_CONSECUENCIA_EN
    assert relation.layer_ids == ["layer_metafisica", "layer_fisica"]

    restored = NarrativeRelation.from_dict(relation.to_dict())
    assert restored.relation_type is RelationType.PRODUCE_CONSECUENCIA_EN
    assert restored.layer_ids == ["layer_metafisica", "layer_fisica"]


@pytest.mark.application
def test_context_builder_adds_upper_causes_when_worldbuilding_is_on() -> None:
    project = _project()
    cause = _entity("cause", "Dos agujeros negros son dioses combatiendo", "layer_metafisica")
    effect = _entity("effect", "La gravedad es inestable", "layer_fisica")
    project.entities.extend([cause, effect])
    project.relations.append(NarrativeRelation(
        id="rel_causal",
        source_id=cause.id,
        target_id=effect.id,
        relation_type=RelationType.EXPLICA,
        layer_ids=["layer_metafisica", "layer_fisica"],
    ))

    context = NarrativeContextBuilder(ProjectServiceStub(project)).build_context("entity", effect.id)
    causal = context["causal_context"]

    assert causal["enabled"] is True
    assert any(entity["id"] == cause.id for entity in causal["upper_cause_entities"])
    assert any(relation["id"] == "rel_causal" and relation["causal_style"] for relation in causal["causal_relations"])
    assert "huérfano" in causal["orphan_detection_hint"]


@pytest.mark.application
def test_context_builder_keeps_causal_context_enabled_always() -> None:
    # PA02: worldbuilding es siempre activo; el contexto causal no se deshabilita
    # aunque el flag heredado venga en False.
    project = _project()
    project.worldbuilding_active = False
    effect = _entity("effect", "La gravedad es inestable", "layer_fisica")
    project.entities.append(effect)

    context = NarrativeContextBuilder(ProjectServiceStub(project)).build_context("entity", effect.id)

    assert context["causal_context"]["enabled"] is True


@pytest.mark.application
def test_b36_ai_actions_are_registered_and_prompt_uses_causal_context() -> None:
    project = _project()
    cause = _entity("cause", "Causa primera", "layer_metafisica")
    effect = _entity("effect", "Consecuencia física", "layer_fisica")
    project.entities.extend([cause, effect])
    ps = ProjectServiceStub(project)
    service = AIContextActionService(ps, CandidateService(project_service=ps), provider_name="simulated", allow_simulated=True)

    expand = service.run_node_action(effect.id, "expand_causal_down", prompt_hint="hacia Materia/Naturaleza")
    explain = service.run_node_action(effect.id, "explain_from_causes")

    assert isinstance(expand, Ok)
    assert isinstance(explain, Ok)
    assert expand.value.action_type == "expand_causal_down"
    assert explain.value.action_type == "explain_from_causes"


@pytest.mark.application
def test_desktop_ui_exposes_b36_layer_view_controls_without_modals() -> None:
    root = Path(__file__).resolve().parents[2]
    workspace = (root / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py").read_text(encoding="utf-8")
    node_panel = (root / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py").read_text(encoding="utf-8")
    tree_panel = (root / "hosts" / "DesktopHostPySide" / "widgets" / "tree_detail_panel.py").read_text(encoding="utf-8")
    graph_canvas = (root / "hosts" / "DesktopHostPySide" / "widgets" / "graph_canvas.py").read_text(encoding="utf-8")

    assert "Vista Anillos causales" in workspace
    assert "set_worldbuilding_active" in workspace
    assert "self.layer_combo" in node_panel
    assert "self.layer_combo" in tree_panel
    assert "Expandir hacia anillo inferior" not in node_panel
    assert "Explicar desde causas superiores" not in node_panel
    assert "Destino causal" not in node_panel
    assert "Expandir hacia anillo inferior" not in tree_panel
    assert "Explicar desde causas superiores" not in tree_panel
    assert "Destino causal" not in tree_panel
    assert "_set_graph_by_layers" in graph_canvas
    panel_sources = node_panel + tree_panel
    assert "QInputDialog" not in panel_sources
    assert "QMessageBox" not in panel_sources
