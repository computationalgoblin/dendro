"""BETA-CIERRE WS-M: marcador de entidad reservada (secreta) visible en el Mapa.

El `_visibility_dot` se creaba pero NUNCA se mostraba: una entidad secreta se veía
igual que una pública. Ahora las entidades reservadas (las que se ocultan a la IA,
ver ai_privacy) llevan punto + candado — distinción por presencia/ausencia y glifo,
no solo color (seguro para daltonismo).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _node(visibility: str):
    from hosts.DesktopHostPySide.widgets.graph_canvas import _NodeView

    return _NodeView(
        entity=SimpleNamespace(),
        entity_id="e1",
        name="X",
        kind="personaje",
        subtitle="",
        canon="canonico",
        visibility=visibility,
    )


def _item(visibility: str):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphNodeItem

    return GraphNodeItem(_node(visibility), x=0.0, y=0.0)


@pytest.mark.parametrize("visibility", ["secreto", "privado", "oculto", "no_exportable"])
def test_reserved_entity_shows_marker_and_lock(app, visibility):
    item = _item(visibility)
    assert hasattr(item, "_visibility_dot")
    assert item._visibility_dot.isVisible()  # antes: siempre oculto
    assert hasattr(item, "_secret_lock")  # candado (no solo color)


def test_public_entity_has_no_marker(app):
    item = _item("publico")
    assert not hasattr(item, "_visibility_dot")  # público → sin marcador
    assert not hasattr(item, "_secret_lock")


def test_marker_keys_match_ai_withheld_policy():
    # El marcador cubre exactamente los estados que WS-B oculta a la IA.
    from hosts.DesktopHostPySide.widgets.graph_canvas import _SECRET_VISIBILITY_KEYS

    assert {"secreto", "privado", "oculto", "no_exportable", "preparado_no_revelado"} <= set(
        _SECRET_VISIBILITY_KEYS
    )


# ── WS-M: canal daltónico del jardín (glifo además del color) ────────────────


def test_watering_glyph_distinguishes_thirsty_from_dried(app):
    item = _item("publico")
    item.set_watering_tint("sedienta")
    glyph = item._watering_glyph_item
    assert glyph is not None and glyph.isVisible()
    assert glyph.text() == "!"  # urge regar
    item.set_watering_tint("secada")
    assert item._watering_glyph_item.text() == "×"  # secada a propósito (distinto glifo)
    # Glifos DISTINTOS → distinción por forma, no solo por color (daltonismo).
    assert _item("publico") is not None


def test_watering_glyph_hidden_when_no_tint(app):
    item = _item("publico")
    item.set_watering_tint("sedienta")
    assert item._watering_glyph_item.isVisible()
    item.set_watering_tint("")  # vuelta a normal → sin glifo
    assert not item._watering_glyph_item.isVisible()
