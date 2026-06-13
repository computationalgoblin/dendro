"""BETA1-G04: vista cronológica — layout determinista, sin física.

Contrato: docs/architecture/G01_time_contract.md §7. La capa de cálculo
(`build_chrono_layout`, `YearScale`) es pura y se testea sin Qt.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    MAX_GAP_PX,
    MIN_GAP_PX,
    YearScale,
    build_chrono_layout,
)
from packages.application.entity_service import EntityService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.project_service import ProjectService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.era import Era
from packages.domain.result import Ok

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

ROOT = Path(__file__).resolve().parents[2]


# ── Fixture: mundo con dos anillos, rama, vidas y un hito ────────────────

@pytest.fixture()
def world():
    ps = ProjectService()
    assert isinstance(ps.create("G04 Chrono"), Ok)
    project = ps.active_project
    chronology = project.project_chronology
    chronology.present_year = 10
    chronology.eras = [
        Era(name="Antigua", start_year=-1000, end_year=-1, order=0),
        Era(name="Presente", start_year=0, end_year=None, order=1),
    ]
    layers = WorldLayerService(ps)
    ring1 = layers.create_layer("Físico", "", 1).value
    ring2 = layers.create_layer("Social", "", 2).value
    svc = EntityService(ps, ps.store)
    a = svc.create_entity({"name": "Ancestro", "entity_type": "personaje",
                           "layer_ids": [ring1.id], "birth_year": -100, "death_year": -20}).value
    b = svc.create_entity({"name": "Viva", "entity_type": "personaje",
                           "layer_ids": [ring1.id], "birth_year": 0}).value
    tree = svc.create_entity({"name": "La Orden", "entity_type": "contenedor",
                              "layer_ids": [ring2.id], "birth_year": -50}).value
    c = svc.create_entity({"name": "Miembro", "entity_type": "personaje",
                           "birth_year": -40}).value  # sin anillo: hereda de la rama
    project.relations.append(SimpleNamespace(
        relation_type="contiene", source_id=tree.id, target_id=c.id,
    ))
    hitos = CausalMilestoneService(project_service=ps)
    hito = hitos.create_hito_manual({
        "title": "La Caída", "year": -30,
        "affected_entity_ids": [a.id, c.id],
        "metadata": {"primary_entity_id": a.id},
    }).value
    return SimpleNamespace(ps=ps, project=project, ring1=ring1, ring2=ring2,
                           a=a, b=b, c=c, tree=tree, hito=hito)


# ── YearScale ─────────────────────────────────────────────────────────────

def test_year_scale_is_monotonic_and_compressed():
    scale = YearScale([-1000, -100, -99, 0, 10])
    ys = [scale.y(year) for year in (-1000, -100, -99, 0, 10)]
    assert ys == sorted(ys)
    assert ys[1] - ys[0] <= MAX_GAP_PX  # desierto de 900 años comprimido
    assert ys[2] - ys[1] >= MIN_GAP_PX  # 1 año nunca colapsa a 0
    # Interpolación dentro de tramo: estrictamente entre los anclas
    mid = scale.y(-550)
    assert ys[0] < mid < ys[1]


# ── Layout puro ───────────────────────────────────────────────────────────

def test_layout_groups_lifelines_by_effective_ring(world):
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    assert len(layout.lifelines) == 4
    assert by_id[world.a.id].ring_id == world.ring1.id
    assert by_id[world.b.id].ring_id == world.ring1.id
    assert by_id[world.tree.id].ring_id == world.ring2.id
    assert by_id[world.c.id].ring_id == world.ring2.id  # heredado de la rama
    # Columnas: orden causal (Físico antes que Social), sin "Sin anillo"
    assert [col.name for col in layout.columns] == ["Físico", "Social"]
    assert layout.columns[0].x_center < layout.columns[1].x_center


def test_layout_time_axis_descends(world):
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    ancestor, alive = by_id[world.a.id], by_id[world.b.id]
    # Y desciende con el tiempo
    assert ancestor.y_birth < alive.y_birth < layout.y_present
    # Muerta: termina en su año; viva: llega al presente
    assert not ancestor.alive and ancestor.y_birth < ancestor.y_end < layout.y_present
    assert alive.alive and alive.y_end == pytest.approx(layout.y_present)


def test_layout_eras_are_ordered_strata(world):
    layout = build_chrono_layout(world.project)
    assert [band.name for band in layout.eras] == ["Antigua", "Presente"]
    old, present = layout.eras
    assert old.y0 < old.y1 <= present.y1
    assert old.y0 < present.y0  # estratos descendentes
    # La era abierta cubre el presente
    assert present.y0 <= layout.y_present <= present.y1


def test_layout_milestone_roots_on_lifelines(world):
    layout = build_chrono_layout(world.project)
    by_id = {line.entity_id: line for line in layout.lifelines}
    assert len(layout.milestones) == 1
    mark = layout.milestones[0]
    assert mark.year == -30
    assert mark.x == pytest.approx(by_id[world.a.id].x)  # sobre la principal
    assert by_id[world.c.id].x in [pytest.approx(x) for x in mark.linked_xs]
    # El hito cae dentro de la vida de la principal
    primary = by_id[world.a.id]
    assert primary.y_birth < mark.y < primary.y_end


def test_chrono_module_has_no_physics():
    source = (ROOT / "hosts/DesktopHostPySide/widgets/chrono_canvas.py").read_text(encoding="utf-8")
    assert "PhysicsEngine" not in source
    assert "graph_physics.engine" not in source
    assert "SIN física" in source


# ── Vista Qt ──────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_chrono_view_builds_scene_and_signals(world):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
    view = ChronoCanvasView()
    view.set_project(world.project)
    assert len(view.scene().items()) > 10
    assert hasattr(view, "entityActivated") and hasattr(view, "milestoneActivated")
    # Reconstrucción idempotente (refresh)
    view.set_project(world.project)
    assert len(view.scene().items()) > 10


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_workspace_wires_view_toggle_and_eras():
    """El ◷ ya no abre el panel H03: alterna la vista (G04)."""
    source = (ROOT / "hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
    assert '("◷", "Cronología e hitos", self._open_milestone_chronology_view)' not in source
    assert "_build_view_toggle" in source
    assert "def set_active_view" in source
    assert "creation/active_view" in source  # preferencia persistida
    assert "_build_eras_section" in source  # G03: eras en filtros
    assert "EraQuickCreatePanel" in source and "EraEditPanel" in source
