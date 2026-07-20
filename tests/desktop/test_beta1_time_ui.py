"""BETA1-G03: UI temporal — fila Nace/Muere/Era en paneles y año en hitos.

Contrato: docs/architecture/G01_time_contract.md §6.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
    from hosts.DesktopHostPySide.widgets.milestone_labels import (
        milestone_sort_value,
        milestone_temporal_label,
    )
    from packages.application.project_service import ProjectService
    from packages.domain.causal_milestone import CausalMilestone
    from packages.domain.era import Era
    from packages.domain.result import Ok


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _ctx_with_project(name="G03-TIME"):
    ps = ProjectService()
    assert isinstance(ps.create(name), Ok)
    chronology = ps.active_project.project_chronology
    chronology.present_year = 100
    chronology.eras = [
        Era(name="Antigua", start_year=-1000, end_year=-1, order=0),
        Era(name="Presente", start_year=0, end_year=None, order=1),
    ]
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = SimpleNamespace(ps=ps)
    return ctx, ps, EntityController(ps), RelationController(ps)


def _create_entity(ec, name, *, kind="personaje", **extra):
    result = ec.create({
        "name": name,
        "entity_type": kind,
        "brief_description": "",
        "canon_state": "borrador",
        **extra,
    })
    assert isinstance(result, Ok)
    return result.value


# ── Panel de hoja (BETA1-UX2C: lapso SOLO-LECTURA; se edita en cronología) ──

def test_node_panel_has_no_lifespan_text(qapp):
    # BETA2-FOCO-27: el lapso ya NO se muestra como texto en el formulario — se
    # define en la cronología del PIE del editor. El panel no expone año editable
    # inline ni la etiqueta muerta de lapso.
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Eldrin", birth_year=-500, death_year=-450)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    assert not hasattr(panel, "birth_year_edit")
    assert not hasattr(panel, "lifespan_label")


def test_node_panel_undated_loads_without_lifespan_text(qapp):
    # BETA1-J04/J06 + BETA2-FOCO-27: una hoja sin fecha carga sin etiqueta de
    # lapso (el estado de datación se visualiza en la cronología, no como texto).
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Nueva")  # sin año → pendiente
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    assert not hasattr(panel, "lifespan_label")
    assert ps.active_project.entities[0].birth_year is None


def test_node_panel_syncs_nature_from_lifespan(qapp):
    # BETA2-FOCO-27: aunque el texto de lapso desapareció, el panel sigue
    # sincronizando la naturaleza temporal desde el life_span de la entidad.
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Nueva", birth_year=100)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    assert not hasattr(panel, "lifespan_label")
    assert panel.nature_combo.currentData() == "mortal"


def test_node_panel_save_preserves_lifespan(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Mortal", birth_year=-12, death_year=88)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    panel.name_edit.setText("Mortal II")
    panel.save()
    saved = ps.active_project.entities[0]
    # Guardar el panel NO toca el lapso (se edita estirando el nodo).
    assert saved.birth_year == -12 and saved.death_year == 88


# ── BETA1-J08: taxonomía curada + naturaleza por tipo ─────────────────────

def test_type_combo_offers_all_offered_types(qapp):
    # UI2-20: cualquier entidad ofrece TODOS los tipos ofrecidos (hoja + rama);
    # la ramitud se deriva del tipo elegido. Los tipos ocultos siguen fuera.
    from packages.domain.entity_taxonomy import OFFERED_ENTITY_TYPES
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "X", birth_year=10)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    datas = {panel.type_combo.itemData(i) for i in range(panel.type_combo.count())}
    assert datas == {t.value for t in OFFERED_ENTITY_TYPES}
    # Los tipos de rama ahora SÍ se ofrecen a cualquier entidad.
    assert "faccion" in datas
    assert "localizacion" in datas
    # Los ocultos (rol 'contenedor', subsistemas, retirados) siguen fuera.
    for hidden in ("escena", "contenedor", "evento", "nota"):
        assert hidden not in datas


# BETA2-CLEANUP-PANELES: test_rama_type_combo_uses_branch_set se retiró — el
# TreeDetailPanel (con su tree_type_combo restringido a ramas) ya no existe; la
# edición de ramas vive en el Foco (NodeDetailPanel variant="foco" con type_combo
# unificado).


def test_nature_combo_visible_only_for_beings(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    creature = _create_entity(ec, "Ángel", kind="criatura", birth_year=10)
    panel = NodeDetailPanel(ctx, ec, creature.id, on_saved=lambda: None)
    assert not panel.nature_combo.isHidden()  # ser → visible
    # 3 valores
    natures = {panel.nature_combo.itemData(i) for i in range(panel.nature_combo.count())}
    assert natures == {"mortal", "inmortal", "eterno"}

    obj = _create_entity(ec, "Espada", kind="objeto", birth_year=10)
    panel2 = NodeDetailPanel(ctx, ec, obj.id, on_saved=lambda: None)
    assert panel2.nature_combo.isHidden()  # no-ser → oculto


# ── Panel de rama ─────────────────────────────────────────────────────────
# BETA2-CLEANUP-PANELES: test_tree_panel_shows_and_preserves_lifespan se retiró.
# El cajón de rama (TreeDetailPanel, con lifespan_label de solo lectura) ya no
# existe; en el Foco el lapso de vida se edita en la banda (FocoLifelineBand).


# ── Cronología de hitos (H03 + G03) ──────────────────────────────────────

def test_milestone_sort_prefers_year_with_sort_index_tiebreak(qapp):
    late = CausalMilestone(id="h-late", title="Tarde", year=50)
    early = CausalMilestone(id="h-early", title="Temprano", year=-200)
    same_year_b = CausalMilestone(id="h-b", title="B", year=10, metadata={"sort_index": 2})
    same_year_a = CausalMilestone(id="h-a", title="A", year=10, metadata={"sort_index": 1})
    ordered = sorted([late, same_year_b, early, same_year_a], key=milestone_sort_value)
    assert [h.id for h in ordered] == ["h-early", "h-a", "h-b", "h-late"]


def test_milestone_sort_without_year_falls_back_to_sort_index(qapp):
    # Compatibilidad H03 (Hermes): hitos pre-migración sin año
    late = CausalMilestone(id="h2", title="Tarde", metadata={"sort_index": 20})
    early = CausalMilestone(id="h1", title="Temprano", metadata={"sort_index": 1})
    assert milestone_sort_value(early) < milestone_sort_value(late)


def test_milestone_temporal_label_uses_year_as_fallback(qapp):
    plain = CausalMilestone(title="Sin etiqueta", year=-77)
    assert milestone_temporal_label(plain) == "Año -77"
    labeled = CausalMilestone(title="Con clave", year=-77, metadata={"chronology_key": "Era del Hielo"})
    assert milestone_temporal_label(labeled) == "Era del Hielo"  # la etiqueta manual manda
    unplaced = CausalMilestone(title="Nada")
    assert milestone_temporal_label(unplaced) == "Sin ubicar"
