"""BETA2-SUB-01: caja de hito-marco en la cronología (encierra a sus subhitos)."""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import build_chrono_layout
from packages.domain.causal_milestone import CausalMilestone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


def _ent(eid, name, *, ring="ring1", birth=0, death=None):
    return SimpleNamespace(
        id=eid, name=name, entity_type="personaje",
        layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=death, custom_metadata={},
    )


def _project(entities, milestones, layers=("ring1",), present=400):
    chronology = SimpleNamespace(
        present_year=present,
        eras=[SimpleNamespace(id="e0", name="Era", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    world_layers = [
        SimpleNamespace(id=lid, name=lid, is_visible=True, order=i + 1, metadata={})
        for i, lid in enumerate(layers)
    ]
    return SimpleNamespace(
        entities=list(entities), relations=[], world_layers=world_layers,
        causal_milestones=list(milestones), project_chronology=chronology,
    )


# ── Tests puros (layout) ─────────────────────────────────────────────────────


def test_milestone_box_created_for_marco_with_subhitos():
    guerra = CausalMilestone(id="guerra", title="La Gran Guerra", year=100)
    b1 = CausalMilestone(id="b1", title="Batalla A", year=102, parent_milestone_id="guerra")
    b2 = CausalMilestone(id="b2", title="Batalla B", year=140, parent_milestone_id="guerra")
    layout = build_chrono_layout(_project([], [guerra, b1, b2]))

    assert len(layout.milestone_boxes) == 1
    box = layout.milestone_boxes[0]
    assert box.milestone_id == "guerra"
    assert box.title == "La Gran Guerra"
    assert box.subhito_count == 2
    # el recuadro tiene extensión en el eje del tiempo
    assert box.y1 > box.y0


def test_no_milestone_box_without_subhitos():
    solo = CausalMilestone(id="solo", title="Hito suelto", year=50)
    layout = build_chrono_layout(_project([], [solo]))
    assert layout.milestone_boxes == []


def test_milestone_box_cross_spans_participants():
    e1 = _ent("e1", "Reina", birth=0)
    guerra = CausalMilestone(
        id="guerra", title="Guerra", year=100, affected_entity_ids=["e1"]
    )
    batalla = CausalMilestone(
        id="b", title="Batalla", year=110, parent_milestone_id="guerra",
        affected_entity_ids=["e1"],
    )
    layout = build_chrono_layout(_project([e1], [guerra, batalla]))
    box = layout.milestone_boxes[0]
    x_e1 = next(lf.x for lf in layout.lifelines if lf.entity_id == "e1")
    assert box.x_left <= x_e1 <= box.x_right


# ── Tests de vista (Qt, offscreen) ───────────────────────────────────────────

pytestmark_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _view_with_marco(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    guerra = CausalMilestone(id="guerra", title="La Gran Guerra", year=100)
    b1 = CausalMilestone(id="b1", title="Batalla A", year=110, parent_milestone_id="guerra")
    project = _project([], [guerra, b1])
    view = ChronoCanvasView()
    view._horizontal = True
    view.set_project(project)
    view.resize(1100, 700)
    view.show()
    view.fit_all()
    return view


@pytestmark_qt
def test_milestone_box_item_in_scene(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    view = _view_with_marco(qapp)
    boxes = [
        i for i in view.scene().items()
        if type(i).__name__ == "_MilestoneBoxItem"
    ]
    assert len(boxes) == 1
    assert boxes[0].milestone_id == "guerra"
    assert isinstance(view, ChronoCanvasView)


@pytestmark_qt
def test_milestone_box_click_opens_hito(qapp):
    view = _view_with_marco(qapp)
    box = next(
        i for i in view.scene().items() if type(i).__name__ == "_MilestoneBoxItem"
    )
    out = {}
    view.milestoneActivated.connect(lambda m: out.__setitem__("m", m))
    view.itemAt = lambda _p, it=box: it
    view._dispatch_click(None)
    assert out.get("m") == "guerra"


@pytestmark_qt
def test_milestone_box_below_nodes_in_z(qapp):
    view = _view_with_marco(qapp)
    box = next(
        i for i in view.scene().items() if type(i).__name__ == "_MilestoneBoxItem"
    )
    # La caja queda por debajo (z bajo) → nodos/vidas ganan el clic.
    assert box.zValue() < 10.0
