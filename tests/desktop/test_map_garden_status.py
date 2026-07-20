"""Estado de riego SIEMPRE visible en el Mapa (BETA2-JARDIN-01).

Tinte marrón (falta_regar) / gris-tierra (secada) + congelación física,
caída a la frontera interior de la banda para Nutrida débil, halo dorado
solo en regadas. Items REALES (GraphNodeItem) sobre GraphCanvasView real,
con reports falsos para controlar cada estado.
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


def _view(entries):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, GraphNodeItem

    view = GraphCanvasView()
    for entity_id, canon in entries:
        item = GraphNodeItem(_node_view(entity_id, canon), x=0.0, y=0.0)
        view._nodes[entity_id] = item
    return view


def _report(status: str, *, nutrida=None, iluminada=None) -> SimpleNamespace:
    latest = None
    if nutrida is not None or iluminada is not None:
        scores = {}
        if nutrida is not None:
            scores["nutrida"] = nutrida
        if iluminada is not None:
            scores["iluminada"] = iluminada
        latest = SimpleNamespace(scores=scores)
    return SimpleNamespace(status=status, latest=latest, stale=False)


class TestGardenStatusVisuals:
    def test_tints_freeze_and_droop_by_status(self, qapp):
        view = _view(
            [
                ("sana", "borrador"),
                ("caida", "borrador"),
                ("sedienta", "borrador"),
                ("secada", "borrador"),
            ]
        )
        reports = {
            "sana": _report("regada", nutrida=70, iluminada=80),
            "caida": _report("regada", nutrida=40),
            "sedienta": _report("falta_regar"),
            "secada": _report("secada"),
        }
        view.set_garden_status_provider(lambda ids: reports)

        assert view._garden_frozen == {"sedienta", "secada"}
        assert view._garden_droopy == {"caida"}
        assert view._garden_overlays == {"sana": {"iluminada": 80, "arraigo": None}}
        assert view._nodes["sedienta"]._watering_tint == "sedienta"
        assert view._nodes["secada"]._watering_tint == "secada"
        assert view._nodes["sana"]._watering_tint == ""
        # Caída: la hoja se encoge; la física la apoyará en la frontera.
        assert abs(view._nodes["caida"].scale() - 0.86) < 1e-6
        assert view._nodes["sana"].scale() == 1.0
        # Sin gradientes de opacidad: todas plenas.
        for entity_id in reports:
            assert view._nodes[entity_id].opacity() == 1.0

    def test_thirsty_with_old_scores_hides_metrics(self, qapp):
        # Aunque conserve scores antiguos buenos, al estar por regar NO se
        # pintan ni halo ni caída: primero hay que regar.
        view = _view([("vieja", "borrador")])
        reports = {"vieja": _report("falta_regar", nutrida=90, iluminada=90)}
        view.set_garden_status_provider(lambda ids: reports)
        assert view._garden_overlays == {}
        assert view._garden_droopy == set()
        assert view._nodes["vieja"]._watering_tint == "sedienta"

    def test_ghost_stays_out_of_the_cycle(self, qapp):
        view = _view([("g", "fantasma")])
        # WateringService reporta falta_regar para fantasmas: el lienzo debe
        # ignorarlo (borrador interno, ni tinte ni congelación).
        reports = {"g": _report("falta_regar")}
        view.set_garden_status_provider(lambda ids: reports)
        assert view._garden_frozen == set()
        assert abs(view._nodes["g"].opacity() - 0.45) < 0.01
        assert view._nodes["g"]._watering_tint == ""

    def test_frozen_bodies_are_pinned_and_thaw_on_refresh(self, qapp):
        view = _view([("seca", "borrador"), ("viva", "borrador")])
        state = {"seca": _report("falta_regar"), "viva": _report("regada", nutrida=80)}
        view.set_garden_status_provider(lambda ids: dict(state))
        view._rebuild_physics_world()
        assert view._physics_engine.bodies["seca"].pinned is True
        assert view._physics_engine.bodies["viva"].pinned is False
        # Tras regar: el refresh descongela y reintegra (reheat interno).
        state["seca"] = _report("regada", nutrida=80)
        view.refresh_garden_status()
        assert view._physics_engine.bodies["seca"].pinned is False
        assert view._nodes["seca"]._watering_tint == ""

    def test_droopy_rests_on_inner_band_edge(self, qapp):
        view = _view([("caida", "borrador"), ("sana", "borrador")])
        reports = {
            "caida": _report("regada", nutrida=30),
            "sana": _report("regada", nutrida=90),
        }
        view.set_garden_status_provider(lambda ids: reports)
        view._layout_mode_active = "concentric_rings"
        view._ring_visuals = [
            SimpleNamespace(ring_id="r1", inner_radius=100.0, outer_radius=400.0)
        ]
        view._node_ring_ids = {"caida": "r1", "sana": "r1"}
        view._rebuild_physics_world()
        caida = view._physics_engine.bodies["caida"]
        sana = view._physics_engine.bodies["sana"]
        # La caída reposa en la frontera interior de su banda; la sana en el
        # centro de la corona.
        assert caida.target_radius == pytest.approx(caida.band_inner)
        assert sana.target_radius == pytest.approx(250.0)

    def test_provider_failure_is_failsafe(self, qapp):
        view = _view([("e", "borrador")])

        def _boom(_ids):
            raise RuntimeError("provider roto")

        view.set_garden_status_provider(_boom)
        assert view._garden_overlays == {}
        assert view._garden_frozen == set()
