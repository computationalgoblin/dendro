"""BETA1-UX7: la cronología se dibuja HORIZONTAL (timeline izquierda→derecha).

El layout puro sigue siendo vertical (x=anillo, y=tiempo); la vista transpone
x↔y. Estos tests verifican la disposición en la ESCENA:
- el tiempo avanza en +X (un hito posterior queda más a la derecha),
- las líneas de vida son horizontales (origen y fin comparten Y, difieren en X),
- y, bajando el flag a vertical, el comportamiento se invierte (sin hardcodear).
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

    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import (
        ChronoCanvasView,
        _EraBandItem,
        _LifelineEndHandle,
        _LifelineHead,
        _MilestoneNode,
    )


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _project():
    chronology = SimpleNamespace(present_year=400, eras=[], metadata={})
    a = SimpleNamespace(
        id="a", name="Ancestro", entity_type="personaje", layer_ids=[],
        birth_year=10, death_year=200, custom_metadata={},
    )
    h1 = SimpleNamespace(id="h1", title="Temprano", year=30, affected_entity_ids=["a"], metadata={})
    h2 = SimpleNamespace(id="h2", title="Tardío", year=150, affected_entity_ids=["a"], metadata={})
    return SimpleNamespace(
        entities=[a], relations=[], world_layers=[],
        causal_milestones=[h1, h2], project_chronology=chronology,
    )


def _head(view, eid):
    return next(
        i for i in view.scene().items()
        if isinstance(i, _LifelineHead) and i.entity_id == eid
    )


def _end(view, eid):
    return next(
        i for i in view.scene().items()
        if isinstance(i, _LifelineEndHandle) and i.entity_id == eid
    )


def _node_for(view, milestone_id):
    return next(
        i for i in view.scene().items()
        if isinstance(i, _MilestoneNode) and i.milestone_id == milestone_id
    )


def test_horizontal_is_the_default(qapp):
    view = ChronoCanvasView()
    assert view._horizontal is True


def test_lifeline_is_horizontal(qapp):
    # Origen (nacimiento) y fin (muerte) comparten Y; el fin queda a la DERECHA
    # del origen porque ocurre después en el tiempo.
    view = ChronoCanvasView()
    view.set_project(_project())
    head = _head(view, "a")
    end = _end(view, "a")
    assert head.scenePos().y() == pytest.approx(end.scenePos().y(), abs=0.5)
    assert end.scenePos().x() > head.scenePos().x()


def test_time_advances_left_to_right(qapp):
    # El hito del año 150 queda a la derecha del hito del año 30.
    view = ChronoCanvasView()
    view.set_project(_project())
    early = _node_for(view, "h1")
    late = _node_for(view, "h2")
    assert late.scenePos().x() > early.scenePos().x()
    # Y a la misma altura (mismo carril de la entidad).
    assert late.scenePos().y() == pytest.approx(early.scenePos().y(), abs=0.5)


def test_eras_span_full_cross_axis_and_order_in_time(qapp):
    # Dos eras acotadas: cada estrato cubre todo el eje anillo (alto) y se
    # ordenan a lo largo del tiempo (X). La era anterior queda a la izquierda.
    chronology = SimpleNamespace(
        present_year=10,
        eras=[
            SimpleNamespace(id="e0", name="Antigua", start_year=-100, end_year=-1, order=0),
            SimpleNamespace(id="e1", name="Nueva", start_year=0, end_year=None, order=1),
        ],
        metadata={},
    )
    project = SimpleNamespace(
        entities=[SimpleNamespace(
            id="a", name="A", entity_type="personaje", layer_ids=[],
            birth_year=-50, death_year=None, custom_metadata={},
        )],
        relations=[], world_layers=[], causal_milestones=[],
        project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.set_project(project)
    bands = {b.era_id: b for b in view.scene().items() if isinstance(b, _EraBandItem)}
    antigua = bands["e0"].sceneBoundingRect()
    nueva = bands["e1"].sceneBoundingRect()
    # La era anterior empieza más a la izquierda en el tiempo (X).
    assert antigua.x() < nueva.x()
    # Cada estrato cubre todo el eje anillo (su alto > su ancho propio no es
    # garantía, pero su alto debe abarcar el contenido); basta con que las dos
    # se solapen en Y (ambas cubren el mismo rango de anillo).
    assert antigua.top() == pytest.approx(nueva.top(), abs=1.0)


def test_era_name_and_years_do_not_overlap(qapp):
    # Regresión de la captura: el nombre de la era y su rango de años se
    # solapaban en horizontal (misma altura, distinto tiempo). Deben quedar
    # APILADOS: el rango debajo del nombre y sin intersección.
    chronology = SimpleNamespace(
        present_year=10,
        eras=[SimpleNamespace(
            id="e0", name="Era del Califato", start_year=-100, end_year=-1, order=0,
        )],
        metadata={},
    )
    project = SimpleNamespace(
        entities=[SimpleNamespace(
            id="a", name="A", entity_type="personaje", layer_ids=[],
            birth_year=-50, death_year=None, custom_metadata={},
        )],
        relations=[], world_layers=[], causal_milestones=[],
        project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.set_project(project)
    texts = [it for it in view.scene().items() if isinstance(it, QGraphicsSimpleTextItem)]
    # El nombre puede venir elidido (…); basta con que empiece por "Era".
    name = next(it for it in texts if it.text().startswith("Era"))
    years = next(it for it in texts if "→" in it.text())
    nb = name.sceneBoundingRect()
    yb = years.sceneBoundingRect()
    assert not nb.intersects(yb)        # no se pisan
    assert yb.top() >= nb.bottom() - 1  # el rango va DEBAJO del nombre


def test_lifeline_has_wide_click_target(qapp):
    # En calendario completo las bandas de era cubren todo el lienzo; clicar unos
    # píxeles FUERA de la fina línea de vida no debe caer en la era (muerta, id
    # vacío) sino abrir la entidad. La línea de vida tiene diana ancha.
    from PySide6.QtCore import QPointF

    from hosts.DesktopHostPySide.widgets.chrono_canvas import _LifelineLine

    meta = {"mode": "full_calendar", "era_lengths": "Califato:120\nFitna:120", "current_year": 200}
    chronology = SimpleNamespace(
        present_year=200,
        eras=[SimpleNamespace(id="present", name="Presente", start_year=0, end_year=None, order=0)],
        metadata=meta,
    )
    a = SimpleNamespace(
        id="a", name="Heroe", entity_type="personaje", layer_ids=[],
        birth_year=20, death_year=None, custom_metadata={},
    )
    project = SimpleNamespace(
        entities=[a], relations=[], world_layers=[], causal_milestones=[],
        project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.set_project(project)
    view.resize(1100, 700)
    view.show()
    view.fit_all()
    line = next(i for i in view.scene().items() if isinstance(i, _LifelineLine))
    ln = line.line()
    midx = (ln.x1() + ln.x2()) / 2.0
    midy = (ln.y1() + ln.y2()) / 2.0
    off = QPointF(midx, midy + 6.0)  # 6px perpendicular (horizontal → en Y)
    out = {}
    view.entityActivated.connect(lambda e: out.__setitem__("ent", e))
    view.eraActivated.connect(lambda e: out.__setitem__("era", e))
    view._dispatch_click(view.mapFromScene(off))
    assert out.get("ent") == "a"   # abre la entidad, no la era de debajo
    assert "era" not in out


def test_era_name_is_clickable(qapp):
    # Clicar el NOMBRE de la era debe abrirla (antes la etiqueta no tenía rol y
    # solo respondía el fondo de la banda). Con id de dominio emite ese id; en
    # calendario completo emite "" (el workspace lo lleva a la config de calendario).
    from PySide6.QtWidgets import QGraphicsSimpleTextItem

    from hosts.DesktopHostPySide.widgets.chrono_canvas import _ERA_ID_ROLE

    chronology = SimpleNamespace(
        present_year=10,
        eras=[SimpleNamespace(id="e0", name="Antigua", start_year=-100, end_year=-1, order=0)],
        metadata={},
    )
    project = SimpleNamespace(
        entities=[SimpleNamespace(
            id="a", name="A", entity_type="personaje", layer_ids=[],
            birth_year=-50, death_year=None, custom_metadata={},
        )],
        relations=[], world_layers=[], causal_milestones=[],
        project_chronology=chronology,
    )
    view = ChronoCanvasView()
    view.set_project(project)
    view.resize(1100, 700)
    view.show()
    view.fit_all()
    name = next(
        it for it in view.scene().items()
        if isinstance(it, QGraphicsSimpleTextItem) and it.text().startswith("Antigua")
    )
    assert name.data(_ERA_ID_ROLE) == "e0"   # la etiqueta lleva el id de la era
    out = {}
    view.eraActivated.connect(lambda e: out.__setitem__("era", e))
    view._dispatch_click(view.mapFromScene(name.sceneBoundingRect().center()))
    assert out.get("era") == "e0"


def test_flag_off_restores_vertical(qapp):
    # Con _horizontal=False la vida vuelve a ser vertical: origen y fin comparten
    # X y el fin queda DEBAJO. Demuestra que la orientación no está hardcodeada.
    view = ChronoCanvasView()
    view._horizontal = False
    view.set_project(_project())
    head = _head(view, "a")
    end = _end(view, "a")
    assert head.scenePos().x() == pytest.approx(end.scenePos().x(), abs=0.5)
    assert end.scenePos().y() > head.scenePos().y()
