"""Búsqueda de imágenes en internet para el retrato de entidad (BETA2-IMG-02/04).

Ventanita con barra de búsqueda cuyos resultados son SOLO imágenes. Proveedor
por defecto: **DuckDuckGo Images** (web abierta, entiende español, sin API
key) con fallback automático a Openverse — ver
``packages/infrastructure/ddg_image_client.py``. Rejilla de miniaturas a la
izquierda y panel de PREVISUALIZACIÓN a la derecha (BETA2-IMG-04): al
seleccionar un resultado se descarga la imagen completa UNA vez, se muestra en
grande y queda cacheada; «Usar esta imagen» confirma con esos bytes. El
diálogo devuelve ``(bytes, ext)`` para que ``portrait_flow`` encadene el
editor de encuadre.

Threading con el patrón consagrado del host (subclase ``QThread`` + ``Signal``
propia, como ``_TreeAIWorker``): los workers manejan SOLO bytes — nada de
``QPixmap`` fuera del hilo GUI — y tokens incrementales descartan respuestas
obsoletas (de búsquedas y de selecciones anteriores). El cliente es inyectable
para tests. Uso privado: sin avisos de licencia (decisión de producto).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QBuffer, QSize, Qt, QThread, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK_MUTED,
    INK_SOFT,
    LINE_SOFT,
    SURFACE_HI,
    WHITE,
)
from packages.domain.result import Error
from packages.infrastructure.ddg_image_client import default_image_search_client

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _ext_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in _ALLOWED_EXTS else ""


def _reencode_png(data: bytes) -> bytes | None:
    """Formato desconocido → PNG (solo en el hilo GUI: usa QImage)."""
    image = QImage()
    if not image.loadFromData(data):
        return None
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data())


class _SearchWorker(QThread):
    """Busca fuera del hilo GUI; emite (token, resultados, error)."""

    finished = Signal(int, list, str)

    def __init__(self, client, token: int, query: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._token = token
        self._query = query

    def run(self):  # noqa: N802 (Qt signature)
        result = self._client.search(self._query)
        if isinstance(result, Error):
            self.finished.emit(self._token, [], result.error)
        else:
            self.finished.emit(self._token, list(result.value), "")


class _ThumbsWorker(QThread):
    """Descarga miniaturas una a una; emite (token, índice, bytes)."""

    thumbReady = Signal(int, int, bytes)  # noqa: N815 (convención Qt de señales)

    def __init__(self, client, token: int, images: list, parent=None):
        super().__init__(parent)
        self._client = client
        self._token = token
        self._images = images

    def run(self):  # noqa: N802 (Qt signature)
        for index, image in enumerate(self._images):
            if self.isInterruptionRequested():
                return
            result = self._client.download(image.thumbnail_url)
            if not isinstance(result, Error):
                self.thumbReady.emit(self._token, index, result.value)


class _DownloadWorker(QThread):
    """Descarga la imagen completa elegida; emite (token, bytes, error)."""

    done = Signal(int, bytes, str)

    def __init__(self, client, token: int, url: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._token = token
        self._url = url

    def run(self):  # noqa: N802 (Qt signature)
        result = self._client.download(self._url)
        if isinstance(result, Error):
            self.done.emit(self._token, b"", result.error)
        else:
            self.done.emit(self._token, result.value, "")


class _ScaledImageLabel(QLabel):
    """Preview que reescala su pixmap al tamaño disponible (con aspecto)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(280, 280)
        self.setStyleSheet(
            f"border: 1px dashed {LINE_SOFT}; border-radius: 12px; "
            "background: rgba(255,255,255,0.45);"
        )

    def set_source(self, pixmap: QPixmap | None):
        self._source = pixmap
        self._rescale()

    def _rescale(self):
        if self._source is None or self._source.isNull():
            self.clear()
            return
        self.setPixmap(
            self._source.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):  # noqa: N802 (Qt signature)
        super().resizeEvent(event)
        self._rescale()


class ImageSearchDialog(QDialog):
    """Buscar en internet → rejilla + preview grande → devuelve (bytes, ext)."""

    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self._client = client or default_image_search_client()
        self._token = 0  # generación de búsqueda
        self._sel_token = 0  # generación de selección (descarga de preview)
        self._results: list = []
        self._selected: tuple[bytes, str] | None = None
        # Estado del preview de la fila seleccionada.
        self._preview_row = -1
        self._preview_data: bytes | None = None
        self._preview_url = ""
        self._preview_failed = False
        self._accept_when_ready = False
        self._search_worker: _SearchWorker | None = None
        self._thumbs_worker: _ThumbsWorker | None = None
        self._download_worker: _DownloadWorker | None = None

        self.setWindowTitle("Buscar imagen en internet")
        self.setModal(True)
        self.resize(980, 680)
        self.setStyleSheet(f"QDialog {{ background: {SURFACE_HI}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar imágenes en internet…")
        self.search_edit.returnPressed.connect(self._start_search)
        search_row.addWidget(self.search_edit, 1)
        self.search_btn = QPushButton("Buscar")
        self.search_btn.clicked.connect(self._start_search)
        search_row.addWidget(self.search_btn)
        root.addLayout(search_row)

        self.status_label = QLabel("Escribe qué imagen buscas y pulsa Buscar.")
        self.status_label.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px;")
        root.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results_list = QListWidget()
        self.results_list.setViewMode(QListView.ViewMode.IconMode)
        self.results_list.setIconSize(QSize(180, 180))
        self.results_list.setGridSize(QSize(196, 196))
        self.results_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.results_list.setMovement(QListView.Movement.Static)
        self.results_list.setUniformItemSizes(True)
        self.results_list.itemDoubleClicked.connect(lambda _item: self._pick_current())
        self.results_list.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.results_list)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        preview_layout.setSpacing(8)
        self.preview_image = _ScaledImageLabel()
        preview_layout.addWidget(self.preview_image, 1)
        self.preview_meta = QLabel("Selecciona un resultado para verlo en grande.")
        self.preview_meta.setWordWrap(True)
        self.preview_meta.setStyleSheet(f"color: {INK_SOFT}; font-size: 11px;")
        preview_layout.addWidget(self.preview_meta)
        self.use_btn = QPushButton("Usar esta imagen")
        self.use_btn.setEnabled(False)
        self.use_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; color: {WHITE}; border: none; "
            "border-radius: 8px; padding: 8px 16px; font-weight: 600; }} "
            "QPushButton:disabled { background: #C9C0A0; }"
        )
        self.use_btn.clicked.connect(self._pick_current)
        preview_layout.addWidget(self.use_btn)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([560, 380])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        root.addLayout(footer)

    # ── búsqueda ────────────────────────────────────────────────────────

    def _start_search(self):
        query = self.search_edit.text().strip()
        if not query:
            return
        self._token += 1
        self._sel_token += 1  # invalida el preview de la búsqueda anterior
        self._interrupt_thumbs()
        self._results = []
        self.results_list.clear()
        self._reset_preview("Selecciona un resultado para verlo en grande.")
        self.use_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.status_label.setText("Buscando…")
        self._search_worker = _SearchWorker(self._client, self._token, query, parent=self)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.start()

    def _on_search_finished(self, token: int, results: list, error: str):
        if token != self._token:
            return  # búsqueda obsoleta: el usuario ya lanzó otra
        self.search_btn.setEnabled(True)
        if error:
            self.status_label.setText(error)
            return
        if not results:
            self.status_label.setText("Sin resultados — prueba con otras palabras.")
            return
        self._results = list(results)
        self.status_label.setText(f"{len(results)} resultados. Elige una imagen.")
        for image in self._results:
            item = QListWidgetItem("")
            details = " · ".join(part for part in [image.title, image.creator] if part)
            item.setToolTip(details)
            self.results_list.addItem(item)
        self._thumbs_worker = _ThumbsWorker(self._client, token, self._results, parent=self)
        self._thumbs_worker.thumbReady.connect(self._on_thumb_ready)
        self._thumbs_worker.start()

    def _on_thumb_ready(self, token: int, index: int, data: bytes):
        if token != self._token or index >= self.results_list.count():
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):  # QPixmap SOLO en el hilo GUI
            self.results_list.item(index).setIcon(QIcon(pixmap))
            # Si es la fila seleccionada y aún no llegó la imagen completa,
            # que el preview enseñe al menos la miniatura.
            if index == self._preview_row and self._preview_data is None:
                self.preview_image.set_source(pixmap)

    # ── preview: la selección descarga la imagen completa UNA vez ───────

    def _reset_preview(self, message: str):
        self._preview_row = -1
        self._preview_data = None
        self._preview_url = ""
        self._preview_failed = False
        self._accept_when_ready = False
        self.preview_image.set_source(None)
        self.preview_meta.setText(message)

    def _on_selection_changed(self):
        row = self.results_list.currentRow()
        has_selection = bool(self.results_list.selectedItems())
        self.use_btn.setEnabled(has_selection)
        if not has_selection or row < 0 or row >= len(self._results):
            return
        same_row_alive = self._preview_data is not None or not self._preview_failed
        if row == self._preview_row and same_row_alive:
            return  # misma fila: descarga ya hecha o en vuelo
        self._start_preview_download(row)

    def _start_preview_download(self, row: int):
        image = self._results[row]
        self._sel_token += 1
        self._preview_row = row
        self._preview_data = None
        self._preview_url = image.image_url
        self._preview_failed = False
        self._accept_when_ready = False  # cambiar de selección anula un «Usar» pendiente
        icon = self.results_list.item(row).icon()
        self.preview_image.set_source(icon.pixmap(QSize(512, 512)) if not icon.isNull() else None)
        details = " · ".join(part for part in [image.title, image.creator] if part)
        loading = "Cargando imagen completa…"
        self.preview_meta.setText(f"{details}\n{loading}" if details else loading)
        self._download_worker = _DownloadWorker(
            self._client, self._sel_token, image.image_url, parent=self
        )
        self._download_worker.done.connect(self._on_preview_done)
        self._download_worker.start()

    def _on_preview_done(self, token: int, data: bytes, error: str):
        if token != self._sel_token:
            return  # selección obsoleta
        if error or not data:
            self._preview_failed = True
            self._accept_when_ready = False
            message = error or "La descarga llegó vacía"
            self.status_label.setText(message)
            self.preview_meta.setText(f"{message} — vuelve a intentarlo.")
            return
        self._preview_data = data
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.preview_image.set_source(pixmap)
            in_range = 0 <= self._preview_row < len(self._results)
            image = self._results[self._preview_row] if in_range else None
            details = " · ".join(
                part
                for part in [getattr(image, "title", ""), getattr(image, "creator", "")]
                if part
            )
            size_note = f"{pixmap.width()}×{pixmap.height()} px"
            self.preview_meta.setText(f"{details}\n{size_note}" if details else size_note)
        if self._accept_when_ready:
            self._finalize(data, self._preview_url)

    # ── confirmación ────────────────────────────────────────────────────

    def _pick_current(self):
        row = self.results_list.currentRow()
        if row < 0 or row >= len(self._results):
            return
        if row == self._preview_row and self._preview_data is not None:
            self._finalize(self._preview_data, self._preview_url)
            return
        self.status_label.setText("Descargando imagen…")
        if row != self._preview_row or self._preview_failed:
            self._start_preview_download(row)  # resetea el flag; se re-arma abajo
        self._accept_when_ready = True

    def _finalize(self, data: bytes, url: str):
        ext = _ext_from_url(url)
        if not ext:
            reencoded = _reencode_png(data)
            if reencoded is None:
                self.status_label.setText("Ese formato de imagen no se pudo convertir")
                return
            data, ext = reencoded, ".png"
        self._selected = (data, ext)
        self.accept()

    def selected_image(self) -> tuple[bytes, str] | None:
        """(bytes, extensión) de la imagen elegida, o None si se canceló."""
        return self._selected

    # ── ciclo de vida ───────────────────────────────────────────────────

    def _interrupt_thumbs(self):
        if self._thumbs_worker is not None and self._thumbs_worker.isRunning():
            self._thumbs_worker.requestInterruption()

    def done(self, result: int):  # noqa: N802 (Qt signature)
        # Invalida cualquier respuesta en vuelo y frena las miniaturas antes
        # de que el diálogo muera (los workers son hijos: Qt los espera).
        self._token += 1
        self._sel_token += 1
        self._interrupt_thumbs()
        for worker in (self._search_worker, self._thumbs_worker, self._download_worker):
            if worker is not None and worker.isRunning():
                worker.wait(2000)
        super().done(result)
