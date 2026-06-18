"""Overlay modal centrado DENTRO de la ventana de la app (PA02).

En vez de abrir diálogos como ventanas top-level del SO (que "se salen" de la
app y pueden quedar descentradas o en otro monitor), este widget atenúa el fondo
de la ventana y centra el contenido encima. No es una ventana del sistema: vive
como hijo del widget central y sigue su tamaño.

Uso:
    self.modal_overlay = ModalOverlay(central_widget)
    self.modal_overlay.open_widget(my_panel)   # centra y muestra
    self.modal_overlay.dismiss()               # cierra y emite `closed`
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ModalOverlay(QWidget):
    """Scrim semitransparente con un único contenido centrado."""

    closed = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("modalOverlay")
        # Scrim atenuado; el contenido trae su propio fondo opaco.
        self.setStyleSheet("QWidget#modalOverlay { background: rgba(20, 18, 12, 0.55); }")
        self._content: QWidget | None = None
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(40, 40, 40, 40)
        self._box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

    # ── API ───────────────────────────────────────────────────────────────

    def open_widget(self, content: QWidget) -> None:
        """Monta `content` centrado y muestra el overlay por encima de todo."""
        self.dismiss(emit=False)
        self._content = content
        content.setParent(self)
        self._box.addWidget(content, alignment=Qt.AlignmentFlag.AlignCenter)
        self._cover_parent()
        self.show()
        self.raise_()
        content.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def dismiss(self, *, emit: bool = True) -> None:
        """Cierra el overlay y destruye el contenido montado."""
        was_visible = self.isVisible()
        if self._content is not None:
            self._box.removeWidget(self._content)
            self._content.setParent(None)
            self._content.deleteLater()
            self._content = None
        self.hide()
        if emit and was_visible:
            self.closed.emit()

    @property
    def is_open(self) -> bool:
        return self.isVisible() and self._content is not None

    # ── geometría / eventos ────────────────────────────────────────────────

    def _cover_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        if obj is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            self._cover_parent()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):  # noqa: N802
        # Modal: clic en el scrim NO cierra (evita perder el panel sin querer).
        event.accept()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)
