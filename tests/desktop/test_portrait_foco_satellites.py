"""Tests del retrato en los satélites del Foco (BETA2-IMG-03).

Render offscreen del lienzo de zonas: un satélite con retrato pinta la imagen
recortada en su círculo; los fantasmas conservan el render translúcido sin
foto; los dicts de FocoView transportan las claves de retrato.
"""

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_cache(qapp):
    from hosts.DesktopHostPySide.widgets import portrait_cache

    portrait_cache.clear_portrait_cache()
    yield
    portrait_cache.clear_portrait_cache()


def _red_asset(tmp_path):
    root = tmp_path / "mundo.assets"
    (root / "images").mkdir(parents=True)
    image = QImage(96, 96, QImage.Format.Format_RGB32)
    image.fill(QColor("#CC1111"))
    path = root / "images" / "rojo.png"
    assert image.save(str(path))
    return root, "images/rojo.png"


def _render_satellite(qapp, assets_root, **kwargs):
    from PySide6.QtWidgets import QGraphicsScene

    from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoSatelliteItem

    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(-80, -80, 160, 160))
    scene._portrait_assets_root = assets_root
    scene.addItem(FocoSatelliteItem("e1", "Eldrin", "personaje", **kwargs))
    image = QImage(320, 320, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, 320, 320), scene.sceneRect())
    painter.end()
    return image


class TestSatellitePortrait:
    def test_satelite_con_retrato_pinta_la_imagen(self, qapp, tmp_path):
        root, rel = _red_asset(tmp_path)
        image = _render_satellite(qapp, root, image_path=rel)
        pixel = image.pixelColor(160, 160)  # centro del círculo
        assert pixel.red() > 150 and pixel.green() < 100

    def test_fantasma_no_lleva_foto(self, qapp, tmp_path):
        root, rel = _red_asset(tmp_path)
        with_img = _render_satellite(qapp, root, image_path=rel, is_ghost=True)
        without = _render_satellite(qapp, root, is_ghost=True)
        assert with_img == without

    def test_sin_assets_root_degrada(self, qapp, tmp_path):
        _, rel = _red_asset(tmp_path)
        with_img = _render_satellite(qapp, None, image_path=rel)
        without = _render_satellite(qapp, None)
        assert with_img == without

    def test_constructor_sin_kwargs_de_retrato_sigue_valido(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoSatelliteItem

        item = FocoSatelliteItem("e1", "Eldrin", "personaje")
        assert item.image_path == ""
        assert item.image_crop is None


class TestFocoViewPortraitMeta:
    def test_portrait_meta_lee_custom_metadata(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import _portrait_meta

        entity = SimpleNamespace(
            custom_metadata={
                "_image_path": "images/abc.png",
                "_image_crop": {"cx": 0.3, "cy": 0.7, "zoom": 2.0},
            }
        )
        meta = _portrait_meta(entity)
        assert meta == {"image_path": "images/abc.png", "image_crop": (0.3, 0.7, 2.0)}

    def test_portrait_meta_sin_imagen(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import _portrait_meta

        assert _portrait_meta(SimpleNamespace()) == {"image_path": "", "image_crop": None}

    def test_canvas_set_assets_root(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas

        canvas = FocoCanvas()
        canvas.set_assets_root(tmp_path / "mundo.assets")
        assert canvas._scene._portrait_assets_root == tmp_path / "mundo.assets"
        canvas.set_assets_root(None)
        assert canvas._scene._portrait_assets_root is None
