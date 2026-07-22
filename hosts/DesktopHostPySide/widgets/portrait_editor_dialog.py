"""Editor de encuadre del retrato de entidad (BETA2-IMG-02).

Se abre SIEMPRE que el usuario carga una imagen (archivo local o búsqueda en
internet) y desde «Editar encuadre…». Encuadre = zoom + posición sobre un
marco circular fijo: el usuario arrastra la imagen bajo el marco y acerca con
la rueda o el deslizador. El preview usa la MISMA matemática
(``PortraitCrop.source_rect``) que las superficies que pintan el retrato, así
lo que se ve aquí es exactamente lo que saldrá en el grafo/foco.

No confundir con la «viñeta» de los lienzos (gradiente radial de fondo).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK_MUTED,
    LINE_SOFT,
    SURFACE_HI,
    WHITE,
)
from packages.application.portrait_crop import MAX_ZOOM, PortraitCrop


class PortraitFrameView(QWidget):
    """Preview interactivo: la imagen se mueve bajo un marco circular fijo."""

    cropChanged = Signal()  # noqa: N815 (convención Qt de señales)

    _MARGIN = 18.0

    def __init__(self, pixmap: QPixmap, crop: PortraitCrop | None = None, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._crop = (crop or PortraitCrop()).normalize()
        self._drag_last: QPointF | None = None
        self.setFixedSize(360, 360)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._reclamp_center()

    # ── estado ──────────────────────────────────────────────────────────

    def crop(self) -> PortraitCrop:
        return self._crop

    def set_zoom(self, zoom: float):
        self._crop = PortraitCrop(self._crop.cx, self._crop.cy, zoom).normalize()
        self._reclamp_center()
        self.update()
        self.cropChanged.emit()

    def pan_by(self, dx: float, dy: float):
        """Desplaza la imagen bajo el marco (delta en píxeles de widget)."""
        scale = self._scale()
        width, height = self._pixmap.width(), self._pixmap.height()
        if scale <= 0 or width <= 0 or height <= 0:
            return
        crop = self._crop
        self._crop = PortraitCrop(
            cx=crop.cx - dx / (scale * width),
            cy=crop.cy - dy / (scale * height),
            zoom=crop.zoom,
        ).normalize()
        self._reclamp_center()
        self.update()
        self.cropChanged.emit()

    def _reclamp_center(self):
        # El centro canónico es el del rect YA clampado dentro de la imagen:
        # así el marco nunca muestra vacío y el estado guardado es estable.
        width, height = self._pixmap.width(), self._pixmap.height()
        if width <= 0 or height <= 0:
            return
        x, y, side = self._crop.source_rect(width, height)
        if side <= 0:
            return
        self._crop = PortraitCrop(
            cx=(x + side / 2) / width,
            cy=(y + side / 2) / height,
            zoom=self._crop.zoom,
        )

    def _radius(self) -> float:
        return min(self.width(), self.height()) / 2 - self._MARGIN

    def _scale(self) -> float:
        width, height = self._pixmap.width(), self._pixmap.height()
        if width <= 0 or height <= 0:
            return 0.0
        _, _, side = self._crop.source_rect(width, height)
        return (2 * self._radius()) / side if side > 0 else 0.0

    # ── interacción ─────────────────────────────────────────────────────

    def mousePressEvent(self, event):  # noqa: N802 (Qt signature)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_last = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):  # noqa: N802 (Qt signature)
        if self._drag_last is not None:
            delta = event.position() - self._drag_last
            self._drag_last = event.position()
            self.pan_by(delta.x(), delta.y())

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt signature)
        self._drag_last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def wheelEvent(self, event):  # noqa: N802 (Qt signature)
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.set_zoom(self._crop.zoom * (1.1**steps))

    # ── pintura ─────────────────────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802 (Qt signature)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        radius = self._radius()
        center = QPointF(self.width() / 2, self.height() / 2)
        circle = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        width, height = self._pixmap.width(), self._pixmap.height()
        if self._pixmap.isNull() or width <= 0 or height <= 0:
            painter.setPen(QPen(QColor(LINE_SOFT), 2.0, Qt.PenStyle.DashLine))
            painter.drawEllipse(circle)
            painter.end()
            return
        x, y, side = self._crop.source_rect(width, height)
        scale = (2 * radius) / side
        dest = QRectF(
            circle.left() - x * scale,
            circle.top() - y * scale,
            width * scale,
            height * scale,
        )
        source = QRectF(0, 0, width, height)
        # Fuera del marco: atenuada, para ver qué queda excluido.
        painter.setOpacity(0.35)
        painter.drawPixmap(dest, self._pixmap, source)
        clip = QPainterPath()
        clip.addEllipse(circle)
        painter.save()
        painter.setClipPath(clip)
        painter.setOpacity(1.0)
        painter.drawPixmap(dest, self._pixmap, source)
        painter.restore()
        # Aro blanco del marco (el mismo lenguaje que el perímetro en el grafo).
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(WHITE), 2.0))
        painter.drawEllipse(circle)
        painter.end()


class PortraitEditorDialog(QDialog):
    """Diálogo modal de encuadre: devuelve el ``PortraitCrop`` elegido."""

    def __init__(self, pixmap: QPixmap, crop: PortraitCrop | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Encuadrar retrato")
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {SURFACE_HI}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        self.frame_view = PortraitFrameView(pixmap, crop, parent=self)
        root.addWidget(self.frame_view, 0, Qt.AlignmentFlag.AlignHCenter)

        hint = QLabel("Arrastra para mover · rueda o deslizador para acercar")
        hint.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(hint)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(100, int(MAX_ZOOM * 100))
        self.zoom_slider.setValue(int(self.frame_view.crop().zoom * 100))
        self.zoom_slider.valueChanged.connect(self._on_slider)
        self.frame_view.cropChanged.connect(self._sync_slider)
        root.addWidget(self.zoom_slider)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        save_btn = QPushButton("Guardar")
        save_btn.setDefault(True)
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; color: {WHITE}; border: none; "
            f"border-radius: 8px; padding: 6px 18px; font-weight: 600; }}"
        )
        save_btn.clicked.connect(self.accept)
        buttons.addWidget(save_btn)
        root.addLayout(buttons)

    def _on_slider(self, value: int):
        self.frame_view.blockSignals(True)
        self.frame_view.set_zoom(value / 100.0)
        self.frame_view.blockSignals(False)

    def _sync_slider(self):
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(int(self.frame_view.crop().zoom * 100))
        self.zoom_slider.blockSignals(False)

    def selected_crop(self) -> PortraitCrop:
        return self.frame_view.crop()
