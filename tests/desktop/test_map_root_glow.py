"""Raíz dorada de arraigo en el Mapa (BETA2-JARDIN-02).

Solo la entidad seleccionada o bajo el cursor, solo si está regada con
arraigo >= 60, y solo hacia vecinas de anillos INTERIORES. Con el gate de
animación cerrado no corre el timer (queda el trazo estático).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _node_view(entity_id: str, canon: str = "borrador") -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        name=entity_id,
        kind="personaje",
        color=None,
        proposed=False,
        canon=canon,
        visibility="publico",
        is_event=False,
        image_path="",
        image_crop=None,
    )


def _edge(a: str, b: str) -> SimpleNamespace:
    return SimpleNamespace(edge=SimpleNamespace(source_id=a, target_id=b))


def _report(status: str, *, arraigo=None, iluminada=None) -> SimpleNamespace:
    scores = {}
    if arraigo is not None:
        scores["arraigo"] = arraigo
    if iluminada is not None:
        scores["iluminada"] = iluminada
    latest = SimpleNamespace(scores=scores) if scores else None
    return SimpleNamespace(status=status, latest=latest, stale=False)


def _rooted_view(reports):
    """Mapa concéntrico: 'centro' en el anillo exterior, 'raiz' en el interior
    (relacionada) y 'par' en el mismo anillo exterior (relacionada)."""
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, GraphNodeItem

    view = GraphCanvasView()
    for entity_id in ("centro", "raiz", "par"):
        view._nodes[entity_id] = GraphNodeItem(_node_view(entity_id), x=0.0, y=0.0)
    view._layout_mode_active = "concentric_rings"
    view._ring_visuals = [
        SimpleNamespace(ring_id="interior", inner_radius=60.0, outer_radius=180.0),
        SimpleNamespace(ring_id="exterior", inner_radius=200.0, outer_radius=380.0),
    ]
    view._node_ring_ids = {"centro": "exterior", "raiz": "interior", "par": "exterior"}
    view._edges = [_edge("raiz", "centro"), _edge("centro", "par")]
    view.set_garden_status_provider(lambda ids: reports)
    return view


class TestRootGlow:
    def test_hover_on_rooted_entity_lights_inner_roots_only(self, qapp):
        view = _rooted_view({"centro": _report("regada", arraigo=80)})
        view._set_garden_hover("centro")
        assert view._root_glow_id == "centro"
        # Solo la vecina del anillo interior; la del mismo anillo no es raíz.
        assert view._root_glow_inner == ["raiz"]
        assert view._root_glow_timer.isActive()
        view._set_garden_hover(None)
        assert view._root_glow_id is None
        assert not view._root_glow_timer.isActive()

    def test_selection_also_lights_the_root(self, qapp):
        view = _rooted_view({"centro": _report("regada", arraigo=60)})
        view._set_garden_focus("centro")
        assert view._root_glow_id == "centro"
        assert view._root_glow_timer.isActive()

    def test_weak_or_unwatered_arraigo_never_glows(self, qapp):
        weak = _rooted_view({"centro": _report("regada", arraigo=40)})
        weak._set_garden_hover("centro")
        assert weak._root_glow_id is None
        assert not weak._root_glow_timer.isActive()
        # Por regar: aunque hubiera scores antiguos, no hay métricas visibles.
        thirsty = _rooted_view({"centro": _report("falta_regar", arraigo=90)})
        thirsty._set_garden_hover("centro")
        assert thirsty._root_glow_id is None

    def test_closed_motion_gate_keeps_static_trace_without_timer(self, qapp):
        view = _rooted_view({"centro": _report("regada", arraigo=80)})
        view.set_motion_gate(lambda: False)
        view._set_garden_hover("centro")
        # La información queda (trazo estático pintable)…
        assert view._root_glow_id == "centro"
        assert view._root_glow_inner == ["raiz"]
        # …pero sin movimiento: el timer jamás arranca.
        assert not view._root_glow_timer.isActive()

    def test_free_layout_has_no_roots(self, qapp):
        view = _rooted_view({"centro": _report("regada", arraigo=80)})
        view._layout_mode_active = "free"
        view._set_garden_hover("centro")
        assert view._root_glow_id is None
        assert not view._root_glow_timer.isActive()
