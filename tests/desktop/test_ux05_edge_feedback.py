"""Feedback interactivo del canvas (BETA1-UX05).

Verifica la corrección con más impacto: la zona de click de las relaciones.
``GraphEdgeItem.shape()`` estaba decorada ``@staticmethod``, lo que rompía el
override virtual de Qt y dejaba el hit-area en el grosor del trazo (~2px). Como
método de instancia, el ensanchado (~16px) sí se aplica y las relaciones se
pueden seleccionar. También comprueba que los colores de relación son cálidos.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets import graph_canvas as gc


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _edge_view(**over):
    base = dict(
        color="",
        kind="contiene",
        direction="dirigida",
        proposed=False,
        inter_ring=False,
        causal=False,
        label="rel",
        relation_id="r1",
        source_id="a",
        target_id="b",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _node(name: str, kind: str, x: float, y: float):
    nv = SimpleNamespace(
        entity_id=name, name=name, kind=kind, proposed=False,
        canon="borrador", visibility="publico",
    )
    return gc.GraphNodeItem(nv, x=x, y=y, radius=40)


def test_edge_shape_hit_area_es_generosa() -> None:
    src = _node("a", "personaje", 0.0, 0.0)
    tgt = _node("b", "objeto", 240.0, 0.0)
    edge = gc.GraphEdgeItem(_edge_view(), src, tgt)

    shape = edge.shape()
    mid = edge.path().pointAtPercent(0.5)

    # Un punto a ~6px perpendicular de la línea cae DENTRO de la zona clickable.
    assert shape.contains(QPointF(mid.x(), mid.y() + 6.0)), "hit-area demasiado estrecho"
    # Un punto a ~30px queda FUERA (no es una zona absurdamente ancha).
    assert not shape.contains(QPointF(mid.x(), mid.y() + 30.0)), "hit-area demasiado ancho"


def test_edge_shape_no_es_staticmethod() -> None:
    # Regresión: debe ser un método de instancia (override virtual real),
    # invocable como self.shape() sin argumentos.
    src = _node("a", "personaje", 0.0, 0.0)
    tgt = _node("b", "lugar", 200.0, 0.0)
    edge = gc.GraphEdgeItem(_edge_view(), src, tgt)
    assert edge.shape().elementCount() > 0


def test_colores_de_relacion_son_calidos() -> None:
    # Antes eran fríos (#7C9BFF azul, #8B5CF6 púrpura). Ahora cálidos.
    assert gc._EDGE_COLORS["pertenece_a"] == "#B28A3C"
    assert gc._EDGE_COLORS["deriva_de"] == "#8A6B7C"
    assert "#7C9BFF" not in gc._EDGE_COLORS.values()
    assert "#8B5CF6" not in gc._EDGE_COLORS.values()
