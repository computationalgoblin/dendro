"""Tests del render de retratos en paneles + cache (BETA2-IMG-03).

Cubre ``portrait_cache`` (recorte cuadrado con encuadre, banda vertical,
buckets, degradación con archivo ausente) y las dos superficies de panel:
miniatura de cabecera con encuadre aplicado y banda lateral del variant foco.
"""

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.portrait_crop import PortraitCrop  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


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


def _two_tone_image(tmp_path, name="dos-tonos.png", width=200, height=100):
    """Mitad izquierda roja, mitad derecha azul — para verificar el recorte."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    for x_pos in range(width):
        color = QColor("#CC2222") if x_pos < width // 2 else QColor("#2222CC")
        for y_pos in range(height):
            image.setPixelColor(x_pos, y_pos, color)
    path = tmp_path / name
    assert image.save(str(path))
    return path


class TestPortraitPixmap:
    def test_recorta_segun_el_encuadre(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        path = _two_tone_image(tmp_path)
        # Encuadre pegado a la izquierda (zona roja) con zoom 2 (lado 50 px).
        left = portrait_cache.portrait_pixmap(path, PortraitCrop(0.0, 0.5, 2.0), 64)
        pixel = left.toImage().pixelColor(32, 32)
        assert pixel.red() > 150 and pixel.blue() < 100
        # Encuadre pegado a la derecha (zona azul).
        right = portrait_cache.portrait_pixmap(path, PortraitCrop(1.0, 0.5, 2.0), 64)
        pixel = right.toImage().pixelColor(32, 32)
        assert pixel.blue() > 150 and pixel.red() < 100

    def test_bucket_de_tamano(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        path = _two_tone_image(tmp_path)
        assert portrait_cache.portrait_pixmap(path, None, 58).width() == 64
        assert portrait_cache.portrait_pixmap(path, None, 72).width() == 128
        assert portrait_cache.portrait_pixmap(path, None, 999).width() == 256

    def test_cache_devuelve_la_misma_instancia(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        path = _two_tone_image(tmp_path)
        first = portrait_cache.portrait_pixmap(path, None, 64)
        second = portrait_cache.portrait_pixmap(path, None, 64)
        assert first is second

    def test_ruta_ausente_o_ilegible_da_none(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        assert portrait_cache.portrait_pixmap(None, None, 64) is None
        bad = tmp_path / "no-imagen.png"
        bad.write_text("esto no es un png", encoding="utf-8")
        assert portrait_cache.portrait_pixmap(bad, None, 64) is None

    def test_resolve_stored(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        root = tmp_path / "mundo.assets"
        (root / "images").mkdir(parents=True)
        asset = root / "images" / "abc.png"
        asset.write_bytes(b"x")
        assert portrait_cache.resolve_stored(root, "images/abc.png") == asset
        assert portrait_cache.resolve_stored(root, "images/nada.png") is None
        assert portrait_cache.resolve_stored(None, "images/abc.png") is None
        assert portrait_cache.resolve_stored(root, str(asset)) == asset  # legacy abs
        assert portrait_cache.resolve_stored(root, "") is None


class TestPortraitBandPixmap:
    def test_banda_vertical_con_proporcion(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        path = _two_tone_image(tmp_path)
        band = portrait_cache.portrait_band_pixmap(path, None, 160, 480)
        assert band is not None
        assert band.width() == 160
        assert band.height() >= 448  # alto bucketizado a saltos de 64

    def test_parametros_invalidos_none(self, qapp, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache

        path = _two_tone_image(tmp_path)
        assert portrait_cache.portrait_band_pixmap(None, None, 160, 480) is None
        assert portrait_cache.portrait_band_pixmap(path, None, 0, 480) is None


# ---------------------------------------------------------------------------
# Paneles
# ---------------------------------------------------------------------------


@pytest.fixture
def stack(tmp_path):
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.project_controller import ProjectController

    project_controller = ProjectController()
    project_path = tmp_path / "mundo.json"
    assert isinstance(project_controller.create("Mundo", str(project_path)), Ok)
    entity_controller = EntityController(project_controller.ps)
    created = entity_controller.create({"name": "Eldrin", "entity_type": "personaje"})
    assert isinstance(created, Ok)
    ctx = SimpleNamespace(
        project_controller=project_controller,
        notify=lambda msg, kind="info": None,
        log=lambda level, msg: None,
        advanced_mode=False,
    )
    return SimpleNamespace(
        ctx=ctx,
        entity_controller=entity_controller,
        entity_id=created.value.id,
        project_path=project_path,
        tmp_path=tmp_path,
    )


def _give_portrait(stack, tmp_path):
    from hosts.DesktopHostPySide.widgets import portrait_flow

    source = _two_tone_image(tmp_path, name="retrato.png")
    assert portrait_flow.apply_portrait(
        stack.ctx,
        stack.entity_controller,
        stack.entity_id,
        PortraitCrop(0.25, 0.5, 2.0),
        source_file=source,
    )


def _make_panel(stack, variant, band=None):
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    # UI2-06: la banda de retrato es de la tarjeta del Foco; el panel solo la
    # alimenta vía on_portrait (aquí se le pasa una banda real para verificar).
    return NodeDetailPanel(
        stack.ctx,
        stack.entity_controller,
        stack.entity_id,
        variant=variant,
        on_portrait=(band.set_portrait if band is not None else None),
    )


def _make_band(qapp):
    from hosts.DesktopHostPySide.widgets.foco.portrait_band import PortraitBand

    return PortraitBand()


class TestNodePanelRender:
    def test_miniatura_con_encuadre(self, qapp, stack, tmp_path):
        _give_portrait(stack, tmp_path)
        panel = _make_panel(stack, "drawer")
        assert panel.image_preview.pixmap() is not None
        assert not panel.image_preview.pixmap().isNull()
        assert panel.image_btn.text() == "Cambiar…"

    def test_sin_imagen_placeholder(self, qapp, stack):
        panel = _make_panel(stack, "drawer")
        assert panel.image_btn.text() == "Imagen…"
        assert panel.portrait_band is None

    def test_variant_foco_alimenta_banda_de_la_tarjeta(self, qapp, stack, tmp_path):
        # UI2-06: el panel resuelve el retrato y la banda de la TARJETA lo pinta.
        _give_portrait(stack, tmp_path)
        band = _make_band(qapp)
        panel = _make_panel(stack, "foco", band=band)
        assert panel.portrait_band is None  # la banda ya no vive en el panel
        assert not band.isHidden()

    def test_variant_foco_sin_imagen_banda_oculta(self, qapp, stack):
        band = _make_band(qapp)
        _make_panel(stack, "foco", band=band)
        assert band.isHidden()

    def test_legacy_ruta_absoluta_no_crashea(self, qapp, stack, tmp_path):
        legacy = _two_tone_image(tmp_path, name="legacy.png")
        entity = stack.entity_controller.get(stack.entity_id).value
        metadata = dict(entity.custom_metadata or {})
        metadata["_image_path"] = str(legacy)
        assert isinstance(
            stack.entity_controller.update(
                stack.entity_id, {"custom_metadata": metadata}
            ),
            Ok,
        )
        panel = _make_panel(stack, "drawer")
        assert panel.image_preview.pixmap() is not None

    def test_asset_borrado_degrada_sin_excepcion(self, qapp, stack, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_cache, portrait_flow

        _give_portrait(stack, tmp_path)
        entity = stack.entity_controller.get(stack.entity_id).value
        rel = entity.custom_metadata["_image_path"]
        portrait_flow.resolve_portrait_path(stack.ctx, rel).unlink()
        portrait_cache.clear_portrait_cache()
        band = _make_band(qapp)
        panel = _make_panel(stack, "foco", band=band)
        assert panel.image_btn.text() == "Imagen…"
        assert band.isHidden()
