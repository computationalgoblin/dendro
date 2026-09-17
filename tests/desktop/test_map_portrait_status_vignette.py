"""UI2-03: viñeta de estado de riego sobre nodos con retrato (Mapa).

Con retrato, el relleno de estado (sedienta/secada) quedaba tapado por la
imagen y solo sobrevivía un aro de 2.4px. Ahora, con tinte + retrato, se pinta
una media-luna inferior translúcida del color de tierra y un aro de estado
grueso; sin retrato, el comportamiento clásico persiste.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QGraphicsScene

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_RADIUS = 50.0
_SIZE = 160  # lienzo de render 1:1 con la escena (LOD = 1.0 → tier completo)
_CENTER = _SIZE // 2


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _node(image_path: str = ""):
    return SimpleNamespace(
        name="Aria",
        kind="personaje",
        color="",
        proposed=False,
        canon="canon",
        visibility="publico",
        image_path=image_path,
        image_crop=None,
        is_event=False,
    )


def _green_portrait(tmp_path) -> str:
    src = QImage(64, 64, QImage.Format.Format_ARGB32)
    src.fill(QColor(0, 200, 0))
    path = tmp_path / "retrato.png"
    src.save(str(path))
    return str(path)


def _item_in_scene(node):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphNodeItem

    scene = QGraphicsScene()
    scene._portrait_assets_root = None
    item = GraphNodeItem(node, x=0.0, y=0.0, radius=_RADIUS)
    scene.addItem(item)
    return scene, item


def _render(scene) -> QImage:
    image = QImage(_SIZE, _SIZE, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(
        painter,
        QRectF(0, 0, _SIZE, _SIZE),
        QRectF(-_SIZE / 2, -_SIZE / 2, _SIZE, _SIZE),
    )
    painter.end()
    return image


class TestPortraitStatusVignette:
    def test_tinted_portrait_gets_crescent_and_thick_ring(self, qapp, tmp_path):
        scene, item = _item_in_scene(_node(_green_portrait(tmp_path)))
        item.set_watering_tint("sedienta")
        image = _render(scene)
        # Media-luna inferior: dentro del círculo, zona baja — el verde puro
        # del retrato queda velado por EARTH_TINT (gana canal rojo).
        low = QColor(image.pixel(_CENTER, _CENTER + int(_RADIUS * 0.76)))
        # BETA2-FIX-01: el umbral era `red() > 100`, un número mágico
        # que codificaba el EARTH_TINT CLARO de antes (#CDBB97). Ahora el tinte es
        # oscuro (criterio 6 de contraste), así que se comprueba lo que la prueba
        # quería decir: el verde puro del retrato queda velado por TIERRA (el
        # canal rojo se despega del azul), sin fijar un brillo concreto.
        assert low.red() > low.blue() + 30, f"esperaba velo tierra abajo: {low.name()}"
        # Mitad superior: el retrato sigue viéndose (verde dominante).
        high = QColor(image.pixel(_CENTER, _CENTER - int(_RADIUS * 0.5)))
        assert high.green() > high.red() + 50, "el retrato no debe quedar tapado arriba"
        # Aro de estado grueso en el borde inferior (EARTH, no blanco).
        rim = QColor(image.pixel(_CENTER, _CENTER + int(_RADIUS) - 1))
        assert rim.red() > rim.blue() + 30, f"aro de estado ausente: {rim.name()}"
        assert rim.green() < 160, "el aro no debe ser verde ni blanco"

    def test_untinted_portrait_stays_clean(self, qapp, tmp_path):
        scene, item = _item_in_scene(_node(_green_portrait(tmp_path)))
        image = _render(scene)
        # Sin tinte no hay media-luna: la zona baja sigue verde.
        low = QColor(image.pixel(_CENTER, _CENTER + int(_RADIUS * 0.76)))
        assert low.green() > low.red() + 50, f"sin tinte no debe haber velo: {low.name()}"

    def test_no_portrait_keeps_classic_fill(self, qapp):
        scene, item = _item_in_scene(_node())
        item.set_watering_tint("sedienta")
        image = _render(scene)
        # Comportamiento JARDIN-01 intacto: relleno EARTH_TINT visible.
        # FIX-01: se compara con el TOKEN, no con un brillo fijo — el tinte pasó a
        # ser oscuro para cumplir 3:1 y `red() > 150` codificaba el color viejo.
        from hosts.DesktopHostPySide.widgets.design_system import EARTH_TINT

        expected = QColor(EARTH_TINT)
        inner = QColor(image.pixel(_CENTER, _CENTER + int(_RADIUS * 0.76)))
        assert abs(inner.red() - expected.red()) <= 6
        assert inner.red() > inner.blue()
