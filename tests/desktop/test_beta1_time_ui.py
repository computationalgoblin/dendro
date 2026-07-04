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
    from hosts.DesktopHostPySide.widgets.tree_detail_panel import TreeDetailPanel
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

def test_node_panel_shows_lifespan_readonly(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Eldrin", birth_year=-500, death_year=-450)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    # Ya no hay campos editables de año; un label solo-lectura muestra el lapso.
    assert not hasattr(panel, "birth_year_edit")
    text = panel.lifespan_label.text()
    assert "-500" in text and "-450" in text and "Antigua" in text


def test_node_panel_undated_shows_por_datar(qapp):
    # BETA1-J04/J06: una hoja sin fecha YA NO hereda el presente; el panel
    # muestra el estado 'Por datar' (nunca un presente falso).
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Nueva")  # sin año → pendiente
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    text = panel.lifespan_label.text()
    assert "Por datar" in text


def test_node_panel_alive_shows_present(qapp):
    # Con fecha de inicio y sin fin, el lapso llega "hasta el presente".
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Nueva", birth_year=100)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    text = panel.lifespan_label.text()
    assert "100" in text and "presente" in text.lower()


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

def test_type_combo_offers_only_curated(qapp):
    # BETA1-J08-fix: la HOJA solo ofrece tipos de hoja (personaje, criatura,
    # objeto, tecnologia, idioma); ni ocultos ni tipos de rama.
    from packages.domain.entity_taxonomy import LEAF_ENTITY_TYPES
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "X", birth_year=10)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    datas = {panel.type_combo.itemData(i) for i in range(panel.type_combo.count())}
    assert datas == {t.value for t in LEAF_ENTITY_TYPES}
    for not_leaf in ("escena", "contenedor", "evento", "nota", "faccion", "localizacion"):
        assert not_leaf not in datas


def test_rama_type_combo_uses_branch_set(qapp):
    # BETA1-J08-fix: la rama ofrece solo tipos de CONTENEDOR (distintos de la
    # hoja); ni el vocabulario legacy TREE_TYPES ni tipos de hoja.
    from packages.domain.entity_taxonomy import BRANCH_ENTITY_TYPES
    ctx, ps, ec, rc = _ctx_with_project()
    rama = _create_entity(ec, "Orden", kind="contenedor", birth_year=10)
    panel = TreeDetailPanel(ctx, ec, rc, rama.id, on_saved=lambda: None)
    texts = {panel.tree_type_combo.itemText(i) for i in range(panel.tree_type_combo.count())}
    branch = {t.value for t in BRANCH_ENTITY_TYPES}
    assert branch.issubset(texts)
    for not_branch in ("reino", "familia", "organizacion", "personaje", "objeto", "idioma"):
        assert not_branch not in texts


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

def test_tree_panel_shows_and_preserves_lifespan(qapp):
    ctx, ps, ec, rc = _ctx_with_project()
    branch = _create_entity(ec, "La Orden", kind="contenedor", birth_year=-700, death_year=-100)
    panel = TreeDetailPanel(ctx, ec, rc, branch.id, on_saved=lambda: None)
    assert not hasattr(panel, "birth_year_edit")
    text = panel.lifespan_label.text()
    assert "-700" in text and "Antigua" in text
    panel.name_edit.setText("La Orden Vieja")
    panel._save()
    saved = ps.active_project.entities[0]
    assert saved.birth_year == -700 and saved.death_year == -100


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
