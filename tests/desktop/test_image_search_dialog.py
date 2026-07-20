"""Tests de ImageSearchDialog (BETA2-IMG-02) con cliente Openverse fake.

Cubre: estados (cargando/error/vacío/resultados), token que descarta
respuestas obsoletas, selección que descarga y devuelve (bytes, ext), y
re-codificación a PNG cuando la URL no trae extensión soportada.
"""

import os
import time

import pytest

try:
    from PySide6.QtCore import QBuffer
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.domain.result import Error, Ok  # noqa: E402
from packages.infrastructure.openverse_client import OpenverseImage  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _png_bytes(color="#CC1111"):
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data())


def _image(idx, url="https://img.example/full1.png"):
    return OpenverseImage(
        id=f"i{idx}",
        title=f"Imagen {idx}",
        creator="Autora",
        license="cc0",
        thumbnail_url=f"https://img.example/thumb{idx}.png",
        image_url=url,
    )


class FakeClient:
    """Cliente síncrono e inyectable: sin red, respuestas deterministas."""

    def __init__(self, results=None, search_error="", downloads=None):
        self.results = results or []
        self.search_error = search_error
        self.downloads = downloads or {}
        self.search_calls = []
        self.download_calls = []

    def search(self, query, page=1, page_size=20):
        self.search_calls.append(query)
        if self.search_error:
            return Error(self.search_error)
        return Ok(list(self.results))

    def download(self, url):
        self.download_calls.append(url)
        if url in self.downloads:
            return Ok(self.downloads[url])
        return Error(f"404 {url}")


def _wait_workers(dialog, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        QApplication.processEvents()
        workers = [dialog._search_worker, dialog._thumbs_worker, dialog._download_worker]
        if all(w is None or w.isFinished() for w in workers):
            # las señales encoladas pueden aterrizar justo después de que el
            # worker termine: unas vueltas extra de bombeo las entregan.
            for _ in range(5):
                time.sleep(0.01)
                QApplication.processEvents()
            return
        time.sleep(0.01)


def _dialog(qapp, client):
    from hosts.DesktopHostPySide.widgets.image_search_dialog import ImageSearchDialog

    return ImageSearchDialog(client=client)


def _search(dialog, text="dragón"):
    dialog.search_edit.setText(text)
    dialog._start_search()
    _wait_workers(dialog)


class TestEstados:
    def test_resultados_pueblan_la_rejilla(self, qapp):
        png = _png_bytes()
        client = FakeClient(
            results=[_image(1), _image(2)],
            downloads={
                "https://img.example/thumb1.png": png,
                "https://img.example/thumb2.png": png,
            },
        )
        dialog = _dialog(qapp, client)
        _search(dialog)
        assert dialog.results_list.count() == 2
        assert "2 resultados" in dialog.status_label.text()
        assert not dialog.results_list.item(0).icon().isNull()
        assert "Autora" in dialog.results_list.item(0).toolTip()

    def test_error_de_busqueda_se_muestra(self, qapp):
        dialog = _dialog(qapp, FakeClient(search_error="Sin conexión con Openverse"))
        _search(dialog)
        assert "Sin conexión" in dialog.status_label.text()
        assert dialog.results_list.count() == 0
        assert dialog.search_btn.isEnabled()

    def test_sin_resultados(self, qapp):
        dialog = _dialog(qapp, FakeClient(results=[]))
        _search(dialog)
        assert "Sin resultados" in dialog.status_label.text()

    def test_query_vacia_no_busca(self, qapp):
        client = FakeClient(results=[_image(1)])
        dialog = _dialog(qapp, client)
        dialog.search_edit.setText("   ")
        dialog._start_search()
        assert client.search_calls == []


class TestToken:
    def test_respuesta_obsoleta_se_descarta(self, qapp):
        dialog = _dialog(qapp, FakeClient(results=[_image(1)]))
        _search(dialog)
        assert dialog.results_list.count() == 1
        stale_token = dialog._token - 1
        dialog._on_search_finished(stale_token, [_image(2), _image(3)], "")
        # la respuesta vieja no toca la rejilla actual
        assert dialog.results_list.count() == 1

    def test_miniatura_obsoleta_se_descarta(self, qapp):
        dialog = _dialog(qapp, FakeClient(results=[_image(1)]))
        _search(dialog)
        icon_before = dialog.results_list.item(0).icon().isNull()
        dialog._on_thumb_ready(dialog._token - 1, 0, _png_bytes())
        assert dialog.results_list.item(0).icon().isNull() == icon_before


class TestSeleccion:
    def test_elegir_descarga_y_acepta(self, qapp):
        png = _png_bytes()
        client = FakeClient(
            results=[_image(1, url="https://img.example/full1.png")],
            downloads={"https://img.example/full1.png": png},
        )
        dialog = _dialog(qapp, client)
        _search(dialog)
        dialog.results_list.setCurrentRow(0)
        dialog._pick_current()
        _wait_workers(dialog)
        assert dialog.result() == 1  # aceptado
        data, ext = dialog.selected_image()
        assert data == png
        assert ext == ".png"

    def test_url_sin_extension_se_recodifica_a_png(self, qapp):
        png = _png_bytes()
        client = FakeClient(
            results=[_image(1, url="https://img.example/raw-imagen")],
            downloads={"https://img.example/raw-imagen": png},
        )
        dialog = _dialog(qapp, client)
        _search(dialog)
        dialog.results_list.setCurrentRow(0)
        dialog._pick_current()
        _wait_workers(dialog)
        data, ext = dialog.selected_image()
        assert ext == ".png"
        reloaded = QImage()
        assert reloaded.loadFromData(data)

    def test_descarga_fallida_no_cierra(self, qapp):
        client = FakeClient(results=[_image(1, url="https://img.example/full1.png")])
        dialog = _dialog(qapp, client)
        _search(dialog)
        dialog.results_list.setCurrentRow(0)
        dialog._pick_current()
        _wait_workers(dialog)
        assert dialog.selected_image() is None
        assert dialog.result() == 0
        assert "404" in dialog.status_label.text()
        assert dialog.results_list.isEnabled()


class TestPreview:
    def test_seleccion_descarga_y_cachea_el_preview(self, qapp):
        png = _png_bytes()
        client = FakeClient(
            results=[_image(1, url="https://img.example/full1.png")],
            downloads={"https://img.example/full1.png": png},
        )
        dialog = _dialog(qapp, client)
        _search(dialog)
        dialog.results_list.setCurrentRow(0)
        _wait_workers(dialog)
        assert dialog._preview_data == png
        assert dialog.preview_image.pixmap() is not None
        assert not dialog.preview_image.pixmap().isNull()
        assert "px" in dialog.preview_meta.text()  # dimensiones mostradas

    def test_usar_con_preview_cacheado_no_redescarga(self, qapp):
        png = _png_bytes()
        full = "https://img.example/full1.png"
        client = FakeClient(results=[_image(1, url=full)], downloads={full: png})
        dialog = _dialog(qapp, client)
        _search(dialog)
        dialog.results_list.setCurrentRow(0)
        _wait_workers(dialog)
        downloads_before = client.download_calls.count(full)
        assert downloads_before == 1
        dialog._pick_current()
        _wait_workers(dialog)
        assert dialog.result() == 1
        assert dialog.selected_image() == (png, ".png")
        assert client.download_calls.count(full) == downloads_before  # sin 2ª descarga

    def test_pie_sin_atribucion_openverse(self, qapp):
        from PySide6.QtWidgets import QLabel

        dialog = _dialog(qapp, FakeClient())
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        assert not any("Openverse" in text for text in labels)

    def test_cliente_por_defecto_es_ddg_con_fallback(self, qapp):
        from hosts.DesktopHostPySide.widgets.image_search_dialog import ImageSearchDialog
        from packages.infrastructure.ddg_image_client import DdgImageClient
        from packages.infrastructure.openverse_client import OpenverseClient

        dialog = ImageSearchDialog()
        assert isinstance(dialog._client, DdgImageClient)
        assert isinstance(dialog._client.fallback, OpenverseClient)
