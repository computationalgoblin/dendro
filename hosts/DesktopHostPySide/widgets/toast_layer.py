"""Toasts / avisos transitorios (BETA1-UX13).

Píldoras breves que confirman acciones (éxito), informan o señalan errores, sin
robar el foco ni interrumpir. Se anclan abajo-IZQUIERDA del padre (las semillas
germinantes viven abajo-derecha → sin solape) y se apilan hacia arriba.

Coherente con SeedNotificationLayer: anclaje por eventFilter sobre el padre,
aparición con ``fade_in`` del design system, auto-descarte por timer y descarte
al clic. Sin QGraphicsDropShadowEffect (vacía widgets dinámicos; lección G08).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK,
    INK_STRONG,
    LINE,
    RADIUS_LG,
    SPACE_LG,
    SPACE_SM,
    SURFACE_HI,
    fade_in,
)

_MARGIN = 18
_DEFAULT_DURATION_MS = 3200
_MAX_VISIBLE = 4

_ERROR_BG = "#FBEAE7"
_ERROR_FG = "#7A241B"
_ERROR_ACCENT = "#C0392B"  # rojo botánico, el mismo de las semillas de error
_SUCCESS_ACCENT = GOLD
_INFO_ACCENT = LINE

_KINDS = {
    "success": (SURFACE_HI, INK_STRONG, _SUCCESS_ACCENT),
    "info": (SURFACE_HI, INK, _INFO_ACCENT),
    "error": (_ERROR_BG, _ERROR_FG, _ERROR_ACCENT),
}


class Toast(QFrame):
    """Una píldora transitoria. Emite ``dismissed`` al cerrarse (timer o clic)."""

    dismissed = Signal(object)

    def __init__(
        self,
        message: str,
        *,
        kind: str = "info",
        duration_ms: int = _DEFAULT_DURATION_MS,
        action_label: str = "",
        on_action=None,
        dedup_key: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind if kind in _KINDS else "info"
        # WS-O: clave de de-dup (evita el spam de avisos idénticos en tormentas
        # de error). Vacía → se de-duplica por el propio mensaje.
        self.dedup_key = dedup_key or message
        bg, fg, accent = _KINDS[self.kind]
        self.setObjectName("toast")
        # Barra de acento a la izquierda (borde grueso) + fondo cálido redondeado.
        self.setStyleSheet(
            f"QFrame#toast {{ background: {bg}; border: 1px solid {LINE}; "
            f"border-left: 3px solid {accent}; border-radius: {RADIUS_LG}px; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        box = QHBoxLayout(self)
        box.setContentsMargins(SPACE_LG, SPACE_SM, SPACE_LG, SPACE_SM)
        box.setSpacing(SPACE_SM)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {fg}; background: transparent; border: none; font-size: 13px;")
        box.addWidget(label, 1)
        # WS-O: acción persistente (p. ej. «Abrir registro») para los avisos de
        # recuperación — un banner que se queda hasta que el usuario actúa/descarta.
        if action_label:
            self.action_button = QPushButton(action_label, self)
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_button.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {accent}; "
                f"border-radius: 10px; color: {fg}; font-size: 12px; font-weight: 700; "
                f"padding: 3px 10px; }} "
                f"QPushButton:hover {{ background: {GOLD}; color: {INK_STRONG}; }}"
            )

            def _run_action():
                if callable(on_action):
                    on_action()
                self._dismiss()

            self.action_button.clicked.connect(_run_action)
            box.addWidget(self.action_button, 0)
        self.setMaximumWidth(460)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        if duration_ms > 0:
            self._timer.start(max(800, int(duration_ms)))

    def show_animated(self) -> None:
        self.show()
        fade_in(self)

    def _dismiss(self) -> None:
        self._timer.stop()
        self.dismissed.emit(self)

    def mousePressEvent(self, event):  # noqa: N802 (Qt signature)
        if event.button() == Qt.MouseButton.LeftButton:
            self._dismiss()
            event.accept()
            return
        super().mousePressEvent(event)


class ToastLayer(QWidget):
    """Pila de toasts anclada a la esquina inferior DERECHA del padre (UX33: junto a
    las acciones del canvas, p. ej. el botón Guardar)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toastLayer")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("QWidget#toastLayer { background: transparent; }")
        self._toasts: list[Toast] = []
        self._bottom_offset = 0
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(SPACE_SM)
        self._box.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

    # ── API ──────────────────────────────────────────────────────────────
    @property
    def toasts(self) -> list[Toast]:
        return list(self._toasts)

    def show_toast(
        self,
        message: str,
        *,
        kind: str = "info",
        duration_ms: int = _DEFAULT_DURATION_MS,
        action_label: str = "",
        on_action=None,
        dedup_key: str = "",
    ) -> Toast:
        # WS-O: de-dup — si ya hay un aviso idéntico en pantalla, no lo repetimos
        # (evita la tormenta de toasts cuando algo falla en bucle).
        key = dedup_key or message
        for existing in self._toasts:
            if getattr(existing, "dedup_key", None) == key:
                return existing
        # Limita la pila: descarta el más antiguo si se supera el máximo.
        while len(self._toasts) >= _MAX_VISIBLE:
            self._remove(self._toasts[0])
        toast = Toast(
            message,
            kind=kind,
            duration_ms=duration_ms,
            action_label=action_label,
            on_action=on_action,
            dedup_key=key,
            parent=self,
        )
        toast.dismissed.connect(self._remove)
        self._toasts.append(toast)
        self._box.addWidget(toast, alignment=Qt.AlignmentFlag.AlignRight)
        self._reflow()
        toast.show_animated()
        return toast

    def show_recovery(self, message: str, *, on_open_log=None) -> Toast:
        """WS-O: aviso de recuperación PERSISTENTE (no se desvanece) con «Abrir
        registro» y de-dup. Sustituye al toast fugaz con ruta incopiable para los
        fallos serios (apertura/guardado)."""
        return self.show_toast(
            message,
            kind="error",
            duration_ms=0,  # persistente hasta que el usuario actúa/descarta
            action_label="Abrir registro",
            on_action=on_open_log,
            dedup_key=f"recovery::{message}",
        )

    def set_bottom_offset(self, px: int) -> None:
        self._bottom_offset = max(0, int(px))
        self._reposition()

    def clear(self) -> None:
        for toast in list(self._toasts):
            self._remove(toast)

    # ── internos ───────────────────────────────────────────────────────────
    def _remove(self, toast: Toast) -> None:
        if toast not in self._toasts:
            return
        self._toasts.remove(toast)
        self._box.removeWidget(toast)
        toast.setParent(None)
        toast.deleteLater()
        self._reflow()

    def _reflow(self) -> None:
        if not self._toasts:
            self.hide()
            return
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        # UX33: anclado abajo-DERECHA (cerca del botón Guardar del canvas).
        x = parent.width() - self.width() - _MARGIN
        y = parent.height() - self.height() - _MARGIN - self._bottom_offset
        self.move(max(0, x), max(0, y))

    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        if obj is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            self._reposition()
        return super().eventFilter(obj, event)


__all__ = ["ToastLayer", "Toast"]
