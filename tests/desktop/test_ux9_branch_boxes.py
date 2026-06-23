"""BETA1-UX9: cajas de contención de ramas en la cronología.

La capa de cálculo (`build_chrono_layout`) agrupa los miembros de una rama
(contenedor) en carriles contiguos y produce un `BranchBox` por rama. Pura: se
testea sin Qt. Los tests de vista (clic, z-order, ambas orientaciones) van al
final, protegidos por PySide6.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    LANE_WIDTH,
    build_chrono_layout,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


# ── Helpers de construcción (SimpleNamespace, sin servicios) ────────────────

def _ent(eid, name, *, kind="personaje", ring=None, birth=0, death=None):
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind,
        layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=death, custom_metadata={},
    )


def _contiene(src, tgt):
    return SimpleNamespace(relation_type="contiene", source_id=src, target_id=tgt)


def _project(entities, relations=(), layers=("ring1",), present=400):
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
        entities=list(entities), relations=list(relations), world_layers=world_layers,
        causal_milestones=[], project_chronology=chronology,
    )


def _xby(layout):
    return {lf.entity_id: lf.x for lf in layout.lifelines}


# ── Tests puros ─────────────────────────────────────────────────────────────

def test_box_created_for_contenedor_with_members():
    tree = _ent("t", "Casa", kind="contenedor", ring="ring1", birth=0)
    ned = _ent("ned", "Ned", birth=20, death=120)
    arya = _ent("arya", "Arya", birth=80)
    layout = build_chrono_layout(_project(
        [tree, ned, arya], [_contiene("t", "ned"), _contiene("t", "arya")]
    ))
    assert len(layout.boxes) == 1
    box = layout.boxes[0]
    assert box.branch_id == "t"
    assert box.depth == 0
    assert box.member_count == 2
    assert box.ring_id == "ring1"


def test_members_are_contiguous_with_header_first():
    tree = _ent("t", "Casa", kind="contenedor", ring="ring1", birth=0)
    ned = _ent("ned", "Ned", birth=20)
    arya = _ent("arya", "Arya", birth=80)
    layout = build_chrono_layout(_project(
        [tree, ned, arya], [_contiene("t", "ned"), _contiene("t", "arya")]
    ))
    x = _xby(layout)
    # Cabecera (rama) primero, luego miembros por año de nacimiento, contiguos.
    assert x["t"] < x["ned"] < x["arya"]
    assert x["ned"] - x["t"] == pytest.approx(LANE_WIDTH)
    assert x["arya"] - x["ned"] == pytest.approx(LANE_WIDTH)


def test_box_time_equals_branch_lifespan():
    tree = _ent("t", "Casa", kind="contenedor", ring="ring1", birth=0, death=100)
    # Un miembro vive MÁS que la rama: la caja NO se estira hasta él (decisión #5).
    longevo = _ent("m", "Longevo", birth=10, death=300)
    layout = build_chrono_layout(_project([tree, longevo], [_contiene("t", "m")]))
    box = layout.boxes[0]
    tree_lf = next(lf for lf in layout.lifelines if lf.entity_id == "t")
    member_lf = next(lf for lf in layout.lifelines if lf.entity_id == "m")
    assert box.y0 == pytest.approx(tree_lf.y_birth)
    assert box.y1 == pytest.approx(tree_lf.y_end)
    # El miembro sobresale en tiempo (vive más allá del fin de la rama).
    assert member_lf.y_end > box.y1


def test_box_cross_spans_header_and_members():
    tree = _ent("t", "Casa", kind="contenedor", ring="ring1", birth=0)
    ned = _ent("ned", "Ned", birth=20)
    layout = build_chrono_layout(_project([tree, ned], [_contiene("t", "ned")]))
    x = _xby(layout)
    box = layout.boxes[0]
    assert box.x_left <= x["t"]
    assert box.x_right >= x["ned"]


def test_empty_branch_is_header_only_box():
    tree = _ent("t", "Vacía", kind="contenedor", ring="ring1", birth=0)
    layout = build_chrono_layout(_project([tree]))
    assert len(layout.boxes) == 1
    box = layout.boxes[0]
    assert box.member_count == 0
    # Caja mínima: ancho ~ un carril (rodea solo la cabecera).
    assert box.x_right - box.x_left == pytest.approx(LANE_WIDTH - 2 * 10.0)  # BOX_CROSS_PAD=10


def test_standalone_entities_have_no_box_and_keep_lane_spacing():
    a = _ent("a", "A", ring="ring1", birth=0)
    b = _ent("b", "B", ring="ring1", birth=50)
    layout = build_chrono_layout(_project([a, b]))
    assert layout.boxes == []
    x = _xby(layout)
    assert abs(x["b"] - x["a"]) == pytest.approx(LANE_WIDTH)


def test_cross_ring_member_excluded_from_box():
    # La rama en ring1; el miembro con anillo EXPLÍCITO ring2 → resuelve a ring2 y
    # queda suelto allí, fuera de la caja (decisión #1).
    tree = _ent("t", "Casa", kind="contenedor", ring="ring1", birth=0)
    out = _ent("out", "Fuera", ring="ring2", birth=20)
    layout = build_chrono_layout(_project(
        [tree, out], [_contiene("t", "out")], layers=("ring1", "ring2"),
    ))
    box = next(b for b in layout.boxes if b.branch_id == "t")
    assert box.member_count == 0  # el miembro cross-ring no cuenta
    member_lf = next(lf for lf in layout.lifelines if lf.entity_id == "out")
    assert member_lf.ring_id == "ring2"
    assert not (box.x_left <= member_lf.x <= box.x_right)


def test_nested_subbranch_box():
    b1 = _ent("b1", "Reino", kind="contenedor", ring="ring1", birth=0)
    b2 = _ent("b2", "Casa", kind="contenedor", birth=10)   # subrama (hereda anillo)
    leaf = _ent("leaf", "Hoja", birth=20)
    layout = build_chrono_layout(_project(
        [b1, b2, leaf], [_contiene("b1", "b2"), _contiene("b2", "leaf")],
    ))
    by_id = {b.branch_id: b for b in layout.boxes}
    assert set(by_id) == {"b1", "b2"}
    assert by_id["b1"].depth == 0
    assert by_id["b2"].depth == 1
    # La caja madre contiene en cross a la subcaja.
    assert by_id["b1"].x_left <= by_id["b2"].x_left
    assert by_id["b1"].x_right >= by_id["b2"].x_right


# ── Tests de vista (Qt, offscreen) ──────────────────────────────────────────

pytestmark_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _branch_view(qapp, *, horizontal=True):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
    tree = _ent("t", "Casa Stark", kind="contenedor", ring="ring1", birth=0)
    ned = _ent("ned", "Ned", birth=20, death=120)
    arya = _ent("arya", "Arya", birth=80)
    project = _project([tree, ned, arya], [_contiene("t", "ned"), _contiene("t", "arya")])
    view = ChronoCanvasView()
    view._horizontal = horizontal
    view.set_project(project)
    view.resize(1200, 700)
    view.show()
    view.fit_all()
    return view


@pytestmark_qt
def test_branch_box_item_exists_per_contenedor(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import _BranchBoxItem
    view = _branch_view(qapp)
    boxes = [i for i in view.scene().items() if isinstance(i, _BranchBoxItem)]
    assert len(boxes) == 1
    assert boxes[0].branch_id == "t"


@pytestmark_qt
def test_branch_box_click_opens_branch(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import _BranchBoxItem
    view = _branch_view(qapp)
    box = next(i for i in view.scene().items() if isinstance(i, _BranchBoxItem))
    out = {}
    view.entityActivated.connect(lambda e: out.__setitem__("ent", e))
    view.itemAt = lambda _p, it=box: it
    view._dispatch_click(None)
    assert out.get("ent") == "t"


@pytestmark_qt
def test_branch_box_below_lifelines_in_z(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import _BranchBoxItem, _LifelineHead
    view = _branch_view(qapp)
    box = next(i for i in view.scene().items() if isinstance(i, _BranchBoxItem))
    head = next(
        i for i in view.scene().items()
        if isinstance(i, _LifelineHead) and i.entity_id == "t"
    )
    # La caja queda por debajo → la cabeza/vida de la rama sigue ganando el clic.
    assert box.zValue() < head.zValue()


@pytestmark_qt
def test_branch_box_renders_in_both_orientations(qapp):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import _BranchBoxItem
    for horizontal in (True, False):
        view = _branch_view(qapp, horizontal=horizontal)
        boxes = [i for i in view.scene().items() if isinstance(i, _BranchBoxItem)]
        assert len(boxes) == 1, f"horizontal={horizontal}"
        r = boxes[0].rect()
        assert r.width() > 0 and r.height() > 0
