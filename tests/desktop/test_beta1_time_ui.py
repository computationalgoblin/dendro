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
    from hosts.DesktopHostPySide.widgets.milestone_chronology_view import (
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


# ── Panel de hoja ─────────────────────────────────────────────────────────

def test_node_panel_shows_years_and_derived_era(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Eldrin", birth_year=-500, death_year=-450)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    assert panel.birth_year_edit.text() == "-500"
    assert panel.death_year_edit.text() == "-450"
    assert "Antigua" in panel.era_label.text()


def test_node_panel_defaults_to_present_year_on_create(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Nueva")  # default del servicio (G02)
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    assert panel.birth_year_edit.text() == "100"
    assert panel.death_year_edit.text() == ""  # viva
    assert "Presente" in panel.era_label.text()


def test_node_panel_saves_edited_years(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Mortal")
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    panel.birth_year_edit.setText("-12")
    panel.death_year_edit.setText("88")
    panel.save()
    saved = ps.active_project.entities[0]
    assert saved.birth_year == -12 and saved.death_year == 88
    # Vaciar Muere → vuelve a estar viva
    panel.death_year_edit.setText("")
    panel.save()
    assert ps.active_project.entities[0].death_year is None


# ── Panel de rama ─────────────────────────────────────────────────────────

def test_tree_panel_shows_and_saves_years(qapp):
    ctx, ps, ec, rc = _ctx_with_project()
    branch = _create_entity(ec, "La Orden", kind="contenedor", birth_year=-700)
    panel = TreeDetailPanel(ctx, ec, rc, branch.id, on_saved=lambda: None)
    assert panel.birth_year_edit.text() == "-700"
    assert "Antigua" in panel.era_label.text()
    panel.death_year_edit.setText("-100")
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
