"""B39 — Simplificación del modelo visible: Hoja/Rama/Anillo.

Tests for:
- EntityService.convert_to_branch() — Hoja→Rama transformation
- WorldLayerService.create_ring_from_branch() — Rama→Anillo creation
- AI classify_intent uses new terminology
- UI labels show Hoja/Rama/Anillo
"""
import os
import sys
import pytest
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.domain.entity import NarrativeEntity, EntityType, CanonState
from packages.domain.result import Ok


# ═══════════════════════════════════════════════════════════════════
# Unit: convert_to_branch
# ═══════════════════════════════════════════════════════════════════

class TestConvertToBranch:
    """EntityService.convert_to_branch() unit tests."""

    @staticmethod
    def _make_service():
        from packages.application.project_service import ProjectService
        from packages.application.entity_service import EntityService

        class FakeStore:
            def save(self, project):
                pass
            def load(self):
                return None

        ps = ProjectService(store=FakeStore())
        ps.create("Test B39")
        es = EntityService(ps, ps.store)
        return ps, es

    def test_convert_leaf_to_branch_changes_entity_type(self):
        ps, es = self._make_service()
        result = es.create_entity({
            "name": "Ciudad de Orvhal",
            "entity_type": "lugar",
            "canon_state": "borrador",
        })
        assert isinstance(result, Ok)
        entity_id = result.value.id

        convert = es.convert_to_branch(entity_id)
        assert isinstance(convert, Ok)
        assert convert.value.entity_type == EntityType.CONTENEDOR

    def test_convert_preserves_name_and_description(self):
        ps, es = self._make_service()
        result = es.create_entity({
            "name": "Orvhal",
            "entity_type": "lugar",
            "brief_description": "Ciudad antigua",
            "extended_description": "Una ciudad milenaria",
            "canon_state": "canonico",
        })
        entity_id = result.value.id

        converted = es.convert_to_branch(entity_id).value
        assert converted.name == "Orvhal"
        assert converted.brief_description == "Ciudad antigua"
        assert converted.extended_description == "Una ciudad milenaria"
        assert converted.canon_state == CanonState.CANONICO

    def test_convert_initialises_tree_meta(self):
        ps, es = self._make_service()
        result = es.create_entity({
            "name": "Hermandad",
            "entity_type": "faccion",
        })
        entity_id = result.value.id
        converted = es.convert_to_branch(entity_id).value
        meta = converted.custom_metadata or {}
        # TreeMeta keys use underscore prefix convention
        has_tree = any("tree" in str(k).lower() for k in meta)
        assert has_tree, f"No tree keys found in custom_metadata: {meta}"

    def test_convert_idempotent_on_container(self):
        ps, es = self._make_service()
        result = es.create_entity({
            "name": "Rama existente",
            "entity_type": "contenedor",
        })
        entity_id = result.value.id
        convert = es.convert_to_branch(entity_id)
        assert isinstance(convert, Ok)
        assert convert.value.entity_type == EntityType.CONTENEDOR

    def test_convert_nonexistent_returns_error(self):
        ps, es = self._make_service()
        from packages.domain.result import Error
        result = es.convert_to_branch("nonexistent_id")
        assert isinstance(result, Error)


# ═══════════════════════════════════════════════════════════════════
# Unit: create_ring_from_branch
# ═══════════════════════════════════════════════════════════════════

class TestCreateRingFromBranch:
    """WorldLayerService.create_ring_from_branch() unit tests."""

    @staticmethod
    def _make_service():
        from packages.application.project_service import ProjectService
        from packages.application.world_layer_service import WorldLayerService

        class FakeStore:
            def save(self, project):
                pass
            def load(self):
                return None

        ps = ProjectService(store=FakeStore())
        ps.create("Test B39 Ring")
        ls = WorldLayerService(ps)
        return ps, ls

    def test_create_ring_from_branch_creates_layer(self):
        ps, ls = self._make_service()
        result = ls.create_ring_from_branch(name="Metafísica", description="Estrato superior")
        assert isinstance(result, Ok), f"Got {result}"
        layer = result.value
        assert layer.name == "Metafísica"
        assert layer.description == "Estrato superior"

    def test_created_ring_persists_in_project(self):
        ps, ls = self._make_service()
        ls.create_ring_from_branch(name="Cultura")
        proj = ps.active_project
        assert proj is not None
        assert any(l.name == "Cultura" for l in proj.world_layers)


# ═══════════════════════════════════════════════════════════════════
# Unit: AI classify_intent with new terminology
# ═══════════════════════════════════════════════════════════════════

class TestAIJobClassifyWithNewTerms:
    """classify_intent() recognizes Hoja/Rama/Anillo keywords."""

    def test_faccion_classifies_as_tree(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crea una facción enemiga")
        assert result.intent_type == AIJobType.GENERATE_TREE

    def test_cultura_classifies_as_tree(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crea una cultura nómada")
        assert result.intent_type == AIJobType.GENERATE_TREE

    def test_personaje_classifies_as_entity(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crea tres personajes")
        assert result.intent_type == AIJobType.GENERATE_ENTITIES

    def test_estrato_metafisico_with_worldbuilding(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crea un estrato metafísico", {"worldbuilding_active": True})
        assert result.intent_type == AIJobType.EXPAND_WORLDBUILDING

    def test_estrato_metafisico_without_worldbuilding(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crea un estrato metafísico")
        # Without worldbuilding, falls back to GENERATE_TREE
        assert result.intent_type in (AIJobType.GENERATE_TREE, AIJobType.EXPAND_WORLDBUILDING)

    def test_rama_keyword_classifies_as_tree(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crear una rama nueva")
        assert result.intent_type == AIJobType.GENERATE_TREE

    def test_hoja_keyword_classifies_as_entity(self):
        from packages.application.ai_jobs import classify_intent, AIJobType
        result = classify_intent("Crear una hoja nueva")
        assert result.intent_type == AIJobType.GENERATE_ENTITIES


# ═══════════════════════════════════════════════════════════════════
# Integration: UI labels show Hoja/Rama/Anillo
# ═══════════════════════════════════════════════════════════════════

class TestUILabelsShowNewTerms:
    """Verify source files use Hoja/Rama/Anillo in user-visible strings."""

    def _read(self, *parts):
        return (ROOT / os.path.join(*parts)).read_text(encoding="utf-8")

    def test_workspaces_uses_hoja_not_entidad(self):
        text = self._read("hosts", "DesktopHostPySide", "views", "workspaces.py")
        assert "Nueva hoja" in text
        assert "Crear hoja" in text
        assert '"Nueva entidad"' not in text
        assert '"Crear entidad"' not in text

    def test_workspaces_uses_rama_not_contenedor(self):
        text = self._read("hosts", "DesktopHostPySide", "views", "workspaces.py")
        assert "Crear rama" in text
        assert '"Nueva rama"' in text

    def test_workspaces_uses_anillo_not_capa(self):
        text = self._read("hosts", "DesktopHostPySide", "views", "workspaces.py")
        assert "Anillos causales" in text
        assert "Nuevo anillo" in text

    def test_node_panel_uses_hoja_rama(self):
        text = self._read("hosts", "DesktopHostPySide", "widgets", "node_detail_panel.py")
        assert '"Hoja"' in text
        assert '"Rama"' in text

    def test_node_panel_uses_anillo(self):
        text = self._read("hosts", "DesktopHostPySide", "widgets", "node_detail_panel.py")
        assert '"Anillo:"' in text

    def test_tree_panel_uses_rama(self):
        text = self._read("hosts", "DesktopHostPySide", "widgets", "tree_detail_panel.py")
        assert '"Rama"' in text

    def test_node_panel_has_convert_button(self):
        text = self._read("hosts", "DesktopHostPySide", "widgets", "node_detail_panel.py")
        assert "Convertir en rama" in text

    def test_tree_panel_has_create_ring_button(self):
        text = self._read("hosts", "DesktopHostPySide", "widgets", "tree_detail_panel.py")
        assert "Crear anillo desde rama" in text

    def test_ai_prompt_uses_hoja_rama_anillo(self):
        text = self._read("packages", "application", "ai_jobs.py")
        lower = text.lower()
        assert "hoja" in lower
        assert "rama" in lower
        assert "anillo" in lower

    def test_branch_types_set_correctly(self):
        from packages.application.ai_jobs import BRANCH_TYPES
        assert "faccion" in BRANCH_TYPES
        assert "cultura" in BRANCH_TYPES
        assert "religion" in BRANCH_TYPES
        assert "personaje" not in BRANCH_TYPES
