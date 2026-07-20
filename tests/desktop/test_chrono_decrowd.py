"""BETA2-HOVER-05: de-amontonar la cronología (espaciado + anti-colisión de títulos)."""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    MIN_GAP_PX,
    PX_PER_YEAR,
    YearScale,
)
from packages.domain.causal_milestone import CausalMilestone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


def test_consecutive_years_have_more_air():
    # Con las constantes subidas, dos años consecutivos separan >= MIN_GAP_PX.
    scale = YearScale([0, 1, 2, 3])
    gap = abs(scale.y(1) - scale.y(0))
    assert gap >= MIN_GAP_PX
    assert MIN_GAP_PX >= 40.0
    assert PX_PER_YEAR >= 11.0


# ── Anti-colisión de títulos (vista, offscreen) ──────────────────────────────

pytestmark_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _project(milestones, layers=("ring1",)):
    chronology = SimpleNamespace(
        present_year=400,
        eras=[SimpleNamespace(id="e0", name="Era", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    world_layers = [
        SimpleNamespace(id=lid, name=lid, is_visible=True, order=i + 1, metadata={})
        for i, lid in enumerate(layers)
    ]
    return SimpleNamespace(
        entities=[], relations=[], world_layers=world_layers,
        causal_milestones=list(milestones), project_chronology=chronology,
    )


@pytestmark_qt
def test_same_year_milestone_titles_do_not_overlap(qapp):
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import _MILESTONE_ID_ROLE, ChronoCanvasView

    # 4 hitos EN EL MISMO AÑO: sus títulos deben escalonarse sin solaparse.
    milestones = [
        CausalMilestone(id=f"h{i}", title=f"Hito número {i} de prueba", year=100)
        for i in range(4)
    ]
    view = ChronoCanvasView()
    view.resize(1200, 800)
    view.set_project(_project(milestones))
    view.show()
    view.fit_all()

    title_items = [
        it
        for it in view.scene().items()
        if isinstance(it, QGraphicsSimpleTextItem) and it.data(_MILESTONE_ID_ROLE)
    ]
    assert len(title_items) >= 4
    rects = [it.sceneBoundingRect() for it in title_items]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            inter = rects[i].intersected(rects[j])
            # sin solape real (se toleran <2px por bordes/antialias)
            assert inter.width() < 2.0 or inter.height() < 2.0


@pytestmark_qt
def test_title_does_not_overlap_lifeline_name(qapp):
    # BETA2-HOVER-10: anti-colisión GLOBAL — un título de hito coetáneo de una
    # entidad NO debe pisar el nombre de su línea de vida (antes solo se de-colisionaban
    # los títulos entre sí).
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import (
        _ENTITY_ID_ROLE,
        _MILESTONE_ID_ROLE,
        ChronoCanvasView,
    )

    ent = SimpleNamespace(
        id="e1", name="Entidad Coetánea De Prueba", entity_type="personaje",
        layer_ids=["ring1"], birth_year=100, death_year=None,
        custom_metadata={}, brief_description="",
    )
    proj = _project([CausalMilestone(id="h1", title="Hito del mismo año exacto", year=100)])
    proj.entities = [ent]
    proj.entity_by_id = lambda eid, es=[ent]: next((e for e in es if str(e.id) == str(eid)), None)

    view = ChronoCanvasView()
    view.resize(1200, 800)
    view.set_project(proj)
    view.show()
    view.fit_all()

    names = [
        it for it in view.scene().items()
        if isinstance(it, QGraphicsSimpleTextItem) and it.data(_ENTITY_ID_ROLE)
    ]
    titles = [
        it for it in view.scene().items()
        if isinstance(it, QGraphicsSimpleTextItem) and it.data(_MILESTONE_ID_ROLE)
    ]
    assert names and titles
    for n in names:
        for t in titles:
            inter = n.sceneBoundingRect().intersected(t.sceneBoundingRect())
            assert inter.width() < 2.0 or inter.height() < 2.0
