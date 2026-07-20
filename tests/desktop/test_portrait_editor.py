"""Tests del editor de encuadre y del flujo de retrato (BETA2-IMG-02).

Cubre: crop por defecto, pan/zoom normalizados en el preview, el diálogo, y
la persistencia vía ``portrait_flow.apply_portrait``/``remove_portrait``
(claves ``_image_path`` relativa + ``_image_crop`` en custom_metadata, asset
copiado al proyecto, limpieza de huérfanos y guard sin ruta de proyecto).
"""

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtGui import QColor, QPixmap
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.portrait_crop import MAX_ZOOM, PortraitCrop  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _pixmap(width=200, height=100, color="#AA3355"):
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(color))
    return pixmap


def _frame_view(qapp, width=200, height=100, crop=None):
    from hosts.DesktopHostPySide.widgets.portrait_editor_dialog import PortraitFrameView

    return PortraitFrameView(_pixmap(width, height), crop)


class TestPortraitFrameView:
    def test_crop_por_defecto(self, qapp):
        view = _frame_view(qapp)
        assert view.crop() == PortraitCrop(0.5, 0.5, 1.0)

    def test_pan_desplaza_el_centro(self, qapp):
        view = _frame_view(qapp)
        view.pan_by(-50, 0)
        crop = view.crop()
        assert crop.cx > 0.5
        assert crop.cy == pytest.approx(0.5)

    def test_pan_se_clampa_dentro_de_la_imagen(self, qapp):
        view = _frame_view(qapp)
        view.pan_by(-100000, 0)
        # imagen 200×100, recorte 100 ⇒ el centro no pasa de 0.75
        assert view.crop().cx == pytest.approx(0.75)
        x, _, side = view.crop().source_rect(200, 100)
        assert x + side <= 200

    def test_zoom_se_clampa(self, qapp):
        view = _frame_view(qapp)
        view.set_zoom(99.0)
        assert view.crop().zoom == MAX_ZOOM
        view.set_zoom(0.1)
        assert view.crop().zoom == 1.0

    def test_zoom_conserva_el_centro_valido(self, qapp):
        view = _frame_view(qapp, crop=PortraitCrop(0.9, 0.5, 1.0))
        view.set_zoom(2.0)
        crop = view.crop()
        x, y, side = crop.source_rect(200, 100)
        assert 0 <= x and x + side <= 200
        assert 0 <= y and y + side <= 100


class TestPortraitEditorDialog:
    def test_devuelve_el_crop_del_preview(self, qapp):
        from hosts.DesktopHostPySide.widgets.portrait_editor_dialog import PortraitEditorDialog

        dialog = PortraitEditorDialog(_pixmap(), PortraitCrop(0.6, 0.5, 2.0))
        assert dialog.selected_crop().zoom == pytest.approx(2.0)

    def test_slider_ajusta_el_zoom(self, qapp):
        from hosts.DesktopHostPySide.widgets.portrait_editor_dialog import PortraitEditorDialog

        dialog = PortraitEditorDialog(_pixmap())
        dialog.zoom_slider.setValue(300)
        assert dialog.selected_crop().zoom == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Flujo de persistencia (portrait_flow, sin diálogos)
# ---------------------------------------------------------------------------


@pytest.fixture
def stack(tmp_path):
    """ProjectController real con proyecto en tmp + EntityController + ctx."""
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.project_controller import ProjectController

    project_controller = ProjectController()
    project_path = tmp_path / "mundo.json"
    assert isinstance(project_controller.create("Mundo", str(project_path)), Ok)
    entity_controller = EntityController(project_controller.ps)
    created = entity_controller.create({"name": "Eldrin", "entity_type": "personaje"})
    assert isinstance(created, Ok)
    entity_id = created.value.id
    notifications: list[tuple[str, str]] = []
    ctx = SimpleNamespace(
        project_controller=project_controller,
        notify=lambda msg, kind="info": notifications.append((msg, kind)),
        log=lambda level, msg: notifications.append((msg, level)),
    )
    return SimpleNamespace(
        ctx=ctx,
        entity_controller=entity_controller,
        entity_id=entity_id,
        project_path=project_path,
        notifications=notifications,
    )


def _metadata(stack):
    entity = stack.entity_controller.get(stack.entity_id).value
    return dict(getattr(entity, "custom_metadata", {}) or {})


class TestApplyPortrait:
    def test_persiste_claves_y_copia_el_asset(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        ok = portrait_flow.apply_portrait(
            stack.ctx,
            stack.entity_controller,
            stack.entity_id,
            PortraitCrop(0.4, 0.6, 2.0),
            data=b"png-bytes-1",
            ext=".png",
        )
        assert ok
        meta = _metadata(stack)
        rel = meta["_image_path"]
        assert rel.startswith("images/") and rel.endswith(".png")
        assert meta["_image_crop"] == {"cx": 0.4, "cy": 0.6, "zoom": 2.0}
        assert portrait_flow.resolve_portrait_path(stack.ctx, rel).exists()

    def test_reemplazo_limpia_el_asset_huerfano(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(), data=b"png-bytes-1", ext=".png",
        )
        first_rel = _metadata(stack)["_image_path"]
        first_abs = portrait_flow.resolve_portrait_path(stack.ctx, first_rel)
        portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(), data=b"png-bytes-2", ext=".png",
        )
        assert _metadata(stack)["_image_path"] != first_rel
        assert not first_abs.exists()

    def test_keep_rel_solo_cambia_el_encuadre(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(), data=b"png-bytes-1", ext=".png",
        )
        rel = _metadata(stack)["_image_path"]
        ok = portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(0.2, 0.8, 4.0), keep_rel=rel,
        )
        assert ok
        meta = _metadata(stack)
        assert meta["_image_path"] == rel
        assert meta["_image_crop"]["zoom"] == 4.0

    def test_sin_ruta_de_proyecto_no_persiste(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        stack.ctx.project_controller.current_path = None
        ok = portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(), data=b"png-bytes-1", ext=".png",
        )
        assert not ok
        assert "_image_path" not in _metadata(stack)


class TestRemovePortrait:
    def test_quita_claves_y_borra_el_asset(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        portrait_flow.apply_portrait(
            stack.ctx, stack.entity_controller, stack.entity_id,
            PortraitCrop(), data=b"png-bytes-1", ext=".png",
        )
        rel = _metadata(stack)["_image_path"]
        stored = portrait_flow.resolve_portrait_path(stack.ctx, rel)
        assert portrait_flow.remove_portrait(stack.ctx, stack.entity_controller, stack.entity_id)
        meta = _metadata(stack)
        assert "_image_path" not in meta and "_image_crop" not in meta
        assert not stored.exists()


class TestGuardsYResolucion:
    def test_ensure_project_path_avisa_si_falta(self, qapp, stack):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        stack.ctx.project_controller.current_path = None
        assert portrait_flow.ensure_project_path(stack.ctx) is None
        assert any("Guarda el proyecto" in msg for msg, _ in stack.notifications)

    def test_resolve_legacy_absoluta(self, qapp, stack, tmp_path):
        from hosts.DesktopHostPySide.widgets import portrait_flow

        legacy = tmp_path / "vieja.png"
        legacy.write_bytes(b"x")
        assert portrait_flow.resolve_portrait_path(stack.ctx, str(legacy)) == legacy
        assert portrait_flow.resolve_portrait_path(stack.ctx, str(tmp_path / "no.png")) is None
        assert portrait_flow.resolve_portrait_path(stack.ctx, "") is None
