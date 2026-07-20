"""Tests del retrato en el lienzo del grafo (BETA2-IMG-03).

Render offscreen a QImage: con LOD completo el nodo muestra píxeles del
retrato dentro de la hoja; con LOD bajo (nodo simplificado) y sin assets_root
no se pinta nada nuevo. El view-model transporta ruta y encuadre.
"""

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
    """Asset rojo uniforme bajo una carpeta de assets tipo proyecto."""
    root = tmp_path / "mundo.assets"
    (root / "images").mkdir(parents=True)
    image = QImage(120, 120, QImage.Format.Format_RGB32)
    image.fill(QColor("#CC1111"))
    path = root / "images" / "rojo.png"
    assert image.save(str(path))
    return root, "images/rojo.png"


def _node_view(image_path="", image_crop=None):
    from hosts.DesktopHostPySide.widgets.graph_canvas import _NodeView

    return _NodeView(
        entity=None,
        entity_id="e1",
        name="Eldrin",
        kind="personaje",
        subtitle="",
        canon="canon",
        visibility="publico",
        image_path=image_path,
        image_crop=image_crop,
    )


def _scene_with_node(qapp, view, assets_root):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphNodeItem

    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(-100, -100, 200, 200))
    scene._portrait_assets_root = assets_root
    scene.addItem(GraphNodeItem(view, x=0.0, y=0.0))
    return scene


def _render(scene, scale):
    rect = scene.sceneRect()
    width = max(1, int(rect.width() * scale))
    height = max(1, int(rect.height() * scale))
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, width, height), rect)
    painter.end()
    return image


def _center_pixel(image):
    return image.pixelColor(image.width() // 2, image.height() // 2)


class TestNodeViewTransportaRetrato:
    def test_defaults_sin_imagen(self, qapp):
        view = _node_view()
        assert view.image_path == ""
        assert view.image_crop is None

    def test_entity_view_lee_custom_metadata(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import _entity_view

        entity = SimpleNamespace(
            id="e9",
            name="Ana",
            entity_type="personaje",
            custom_metadata={
                "_image_path": "images/abc.png",
                "_image_crop": {"cx": 0.3, "cy": 0.7, "zoom": 2.0},
            },
        )
        view = _entity_view(entity)
        assert view.image_path == "images/abc.png"
        assert view.image_crop == (0.3, 0.7, 2.0)

    def test_entity_view_sin_imagen(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import _entity_view

        view = _entity_view(SimpleNamespace(id="e2", name="B", entity_type="lugar"))
        assert view.image_path == ""
        assert view.image_crop is None


class TestGraphNodePortraitRender:
    def test_lod_completo_pinta_el_retrato(self, qapp, tmp_path):
        root, rel = _red_asset(tmp_path)
        scene = _scene_with_node(qapp, _node_view(rel), root)
        image = _render(scene, 2.0)  # LOD 2.0 >= _NODE_FULL_LOD
        pixel = _center_pixel(image)
        assert pixel.red() > 150 and pixel.green() < 100

    def test_lod_bajo_no_pinta_retrato(self, qapp, tmp_path):
        root, rel = _red_asset(tmp_path)
        scene = _scene_with_node(qapp, _node_view(rel), root)
        image = _render(scene, 0.2)  # por debajo de _NODE_FULL_LOD
        pixel = _center_pixel(image)
        # nodo simplificado: relleno blanco, sin imagen
        assert pixel.red() > 200 and pixel.green() > 200

    def test_sin_assets_root_degrada_al_render_clasico(self, qapp, tmp_path):
        _, rel = _red_asset(tmp_path)
        scene = _scene_with_node(qapp, _node_view(rel), None)
        pixel = _center_pixel(_render(scene, 2.0))
        assert pixel.green() > 200  # hoja blanca de siempre

    def test_asset_ausente_degrada_sin_excepcion(self, qapp, tmp_path):
        root, _ = _red_asset(tmp_path)
        scene = _scene_with_node(qapp, _node_view("images/no-existe.png"), root)
        pixel = _center_pixel(_render(scene, 2.0))
        assert pixel.green() > 200

    def test_sin_imagen_identico_al_clasico(self, qapp, tmp_path):
        root, _ = _red_asset(tmp_path)
        with_meta = _render(_scene_with_node(qapp, _node_view(), root), 2.0)
        without_root = _render(_scene_with_node(qapp, _node_view(), None), 2.0)
        assert with_meta == without_root


class TestGraphTreePortraitRender:
    def _tree_scene(self, qapp, view, assets_root):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphTreeItem

        scene = QGraphicsScene()
        scene.setSceneRect(QRectF(-200, -150, 400, 300))
        scene._portrait_assets_root = assets_root
        scene.addItem(GraphTreeItem(view, x=0.0, y=0.0))
        return scene

    def test_medallon_cambia_el_render(self, qapp, tmp_path):
        root, rel = _red_asset(tmp_path)
        with_portrait = _render(self._tree_scene(qapp, _node_view(rel), root), 2.0)
        without = _render(self._tree_scene(qapp, _node_view(), root), 2.0)
        assert with_portrait != without

    def test_sin_assets_root_no_crashea(self, qapp, tmp_path):
        _, rel = _red_asset(tmp_path)
        image = _render(self._tree_scene(qapp, _node_view(rel), None), 2.0)
        assert image.width() > 0
