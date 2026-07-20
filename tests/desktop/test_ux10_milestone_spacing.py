"""BETA1-UX10: hitos cercanos en años no solapan su nombre.

Cada hito reserva en el eje del TIEMPO el hueco de su título (la vista lo mide y
lo inyecta como `min_gaps` en `YearScale`). Capa pura testeada sin Qt; el no-solape
real se valida con la vista offscreen.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    MIN_GAP_PX,
    YearScale,
    build_chrono_layout,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


# ── Puro ────────────────────────────────────────────────────────────────────

def test_year_scale_min_gaps_widens_segment():
    base = YearScale([0, 1])
    assert base.y(1) - base.y(0) == pytest.approx(MIN_GAP_PX)
    wide = YearScale([0, 1], min_gaps={0: 200.0})
    assert wide.y(1) - wide.y(0) == pytest.approx(200.0)  # ensancha (supera MAX a propósito)


def test_year_scale_min_gaps_only_after_that_year():
    # El hueco se reserva tras el año indicado, no antes.
    s = YearScale([0, 5, 6], min_gaps={5: 300.0})
    assert s.y(6) - s.y(5) == pytest.approx(300.0)
    assert s.y(5) - s.y(0) < 300.0  # el tramo anterior no se toca


def _milestone_project(years, present=400):
    chronology = SimpleNamespace(
        present_year=present,
        eras=[SimpleNamespace(id="e", name="E", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    a = SimpleNamespace(
        id="a", name="A", entity_type="personaje", layer_ids=["r"],
        birth_year=0, death_year=None, custom_metadata={},
    )
    hitos = [
        SimpleNamespace(
            id=f"h{i}", title=f"Hito {i}", year=y, affected_entity_ids=["a"], metadata={},
        )
        for i, y in enumerate(years)
    ]
    layers = [SimpleNamespace(id="r", name="R", is_visible=True, order=1, metadata={})]
    return SimpleNamespace(
        entities=[a], relations=[], world_layers=layers,
        causal_milestones=hitos, project_chronology=chronology,
    )


def test_build_layout_milestone_min_gaps_separates_close_years():
    proj = _milestone_project([100, 102])
    base = build_chrono_layout(proj)
    wide = build_chrono_layout(proj, milestone_min_gaps={100: 220.0})

    def dist(layout):
        ys = {m.milestone_id: m.y for m in layout.milestones}
        return ys["h1"] - ys["h0"]

    assert dist(base) < 220.0           # sin reserva, años casi pegados
    assert dist(wide) >= 220.0          # con reserva, separados ≥ footprint


def test_build_layout_milestone_span_maps_end_year():
    # FOCO-25: un hito con duración (inicio+fin) expone end_year/y_end para que
    # la vista pinte su franja de lapso; el fin además ancla la escala.
    from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
    from packages.domain.temporal_models import EventTemporality

    proj = _milestone_project([100])
    proj.causal_milestones = [
        CausalMilestone(
            id="h0",
            title="Guerra larga",
            year=100,
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=["a"],
            temporality=EventTemporality(
                year=100, is_duration=True, duration_value=40, duration_unit="años"
            ),
        )
    ]
    layout = build_chrono_layout(proj)
    mark = layout.milestones[0]
    assert mark.end_year == 140
    assert mark.y_end is not None and mark.y_end > mark.y

    # Un hito puntual (sin duración) sigue sin fin.
    proj_point = _milestone_project([100])
    point_layout = build_chrono_layout(proj_point)
    assert point_layout.milestones[0].end_year is None


def test_build_layout_default_is_unchanged():
    # Sin milestone_min_gaps el layout es idéntico al de siempre (protege la suite).
    proj = _milestone_project([10, 11])
    a = build_chrono_layout(proj)
    b = build_chrono_layout(proj, milestone_min_gaps=None)
    assert [m.y for m in a.milestones] == [m.y for m in b.milestones]


# ── Vista (no-solape real) ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytestmark_qt
def test_close_milestone_titles_do_not_overlap(qapp):
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    chronology = SimpleNamespace(
        present_year=400,
        eras=[SimpleNamespace(id="e", name="E", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    a = SimpleNamespace(
        id="a", name="A", entity_type="personaje", layer_ids=["r"],
        birth_year=0, death_year=None, custom_metadata={},
    )
    h1 = SimpleNamespace(
        id="h1", title="Primer hito de nombre muy largo", year=100,
        affected_entity_ids=["a"], metadata={},
    )
    h2 = SimpleNamespace(
        id="h2", title="Segundo hito tambien largo", year=102,
        affected_entity_ids=["a"], metadata={},
    )
    layers = [SimpleNamespace(id="r", name="R", is_visible=True, order=1, metadata={})]
    proj = SimpleNamespace(
        entities=[a], relations=[], world_layers=layers,
        causal_milestones=[h1, h2], project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.resize(1400, 760)
    view.show()
    view.set_project(proj)
    view.fit_all()
    texts = [i for i in view.scene().items() if isinstance(i, QGraphicsSimpleTextItem)]
    t1 = next(i for i in texts if i.text().startswith("Primer hito"))
    t2 = next(i for i in texts if i.text().startswith("Segundo hito"))
    assert not t1.sceneBoundingRect().intersects(t2.sceneBoundingRect())


@pytestmark_qt
def test_same_year_milestone_titles_do_not_overlap(qapp):
    # BETA1-UX10b: el caso real reportado — dos (o más) hitos del MISMO año.
    # No se puede ensanchar el tiempo (misma posición temporal), así que los
    # títulos se apilan en el eje perpendicular. No deben solaparse.
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    chronology = SimpleNamespace(
        present_year=400,
        eras=[SimpleNamespace(id="e", name="E", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    a = SimpleNamespace(
        id="a", name="A", entity_type="personaje", layer_ids=["r"],
        birth_year=0, death_year=None, custom_metadata={},
    )
    titles = [
        "Primer hito de nombre muy largo",
        "Segundo hito tambien bastante largo",
        "Tercer hito igualmente largo aqui",
    ]
    hitos = [
        SimpleNamespace(
            id=f"h{i}", title=t, year=100, affected_entity_ids=["a"], metadata={},
        )
        for i, t in enumerate(titles)
    ]
    layers = [SimpleNamespace(id="r", name="R", is_visible=True, order=1, metadata={})]
    proj = SimpleNamespace(
        entities=[a], relations=[], world_layers=layers,
        causal_milestones=hitos, project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.resize(1400, 760)
    view.show()
    view.set_project(proj)
    view.fit_all()
    title_items = [
        i
        for i in view.scene().items()
        if isinstance(i, QGraphicsSimpleTextItem) and i.text().endswith("largo aqui")
        or isinstance(i, QGraphicsSimpleTextItem) and "hito" in i.text().lower()
    ]
    title_items = [i for i in title_items if i.text().split()[0] in {"Primer", "Segundo", "Tercer"}]
    rects = [i.sceneBoundingRect() for i in title_items]
    assert len(rects) == 3
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not rects[i].intersects(rects[j])
