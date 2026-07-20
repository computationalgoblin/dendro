"""BETA2-FOCO-27: cajón inferior del editor del Foco.

En modo edición, al clicar (o crear) un hito, este cajón SUBE desde el borde
inferior del editor con el panel completo editable del hito. Alto generoso y
desplazable — la información se presenta entera, sin recortes. Hijo del overlay
del editor: se posiciona por geometría (no vive en un layout), se cierra con ✕ o
con Esc. Pintura a mano (sin QGraphicsEffect, regla del repo).
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    EASING_ENTER,
    GOLD_SOFT,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    MOTION_BASE,
    RADIUS_LG,
    SPACE_MD,
    SPACE_SM,
    SURFACE_HI,
    ElidedLabel,
    install_wheel_guard,
)
from hosts.DesktopHostPySide.widgets.qt_lifecycle import _qt_alive

# Fracción del alto del editor que ocupa el cajón cuando está abierto.
_HEIGHT_FRACTION = 0.68
_MIN_HEIGHT = 260


class FocoBottomSheet(QFrame):
    """Cajón que asciende desde el borde inferior del editor."""

    closed = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focoBottomSheet")
        self.setStyleSheet(
            f"QFrame#focoBottomSheet {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-top-left-radius: {RADIUS_LG}px; "
            f"border-top-right-radius: {RADIUS_LG}px; }}"
        )
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_MD)
        self._root.setSpacing(SPACE_SM)

        header = QHBoxLayout()
        self._title = ElidedLabel("", self)
        self._title.setStyleSheet(
            f"color: {INK_STRONG}; font-weight: 700; font-size: 13px; "
            "border: none; background: transparent;"
        )
        header.addWidget(self._title, 1)
        self._close_button = QPushButton("✕", self)
        self._close_button.setFixedSize(24, 24)
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {LINE_SOFT}; border-radius: 12px; "
            f"background: transparent; color: {INK_SOFT}; }} "
            f"QPushButton:hover {{ border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}"
        )
        self._close_button.clicked.connect(self.close_sheet)
        header.addWidget(self._close_button, 0)
        self._root.addLayout(header)

        # El scroll del ANFITRIÓN — el panel de hito ya no anida el suyo, así que
        # aquí se desplaza entero sin recortes.
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self._root.addWidget(self._scroll, 1)

        self._content: QWidget | None = None
        self._animation: QPropertyAnimation | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    # ── contenido ────────────────────────────────────────────────────────────
    def set_content(self, widget: QWidget, title: str = "") -> None:
        self._clear_content()
        self._content = widget
        self._scroll.setWidget(widget)
        install_wheel_guard(widget)  # la rueda no cambia combos/spin del panel
        widget.show()
        self._title.setText(title)

    def _clear_content(self) -> None:
        taken = self._scroll.takeWidget()
        victim = taken if taken is not None else self._content
        self._content = None
        if victim is not None and _qt_alive(victim):
            victim.setParent(self)
            victim.deleteLater()

    def content(self) -> QWidget | None:
        return self._content

    # ── apertura / cierre ────────────────────────────────────────────────────
    def open_over(self, card_rect: QRect) -> None:
        """Despliega el cajón sobre el tercio inferior del rect del editor
        (coords del overlay), ascendiendo desde el borde inferior."""
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        height = max(_MIN_HEIGHT, int(card_rect.height() * _HEIGHT_FRACTION))
        height = min(height, card_rect.height())
        x = card_rect.x()
        width = card_rect.width()
        bottom = card_rect.y() + card_rect.height()
        end = QRect(x, bottom - height, width, height)
        start = QRect(x, bottom, width, 0)
        self.setGeometry(start)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        animation = QPropertyAnimation(self, b"geometry")
        animation.setDuration(MOTION_BASE)
        animation.setEasingCurve(EASING_ENTER)
        animation.setStartValue(start)
        animation.setEndValue(end)
        self._animation = animation
        animation.start()

    def reposition(self, card_rect: QRect) -> None:
        """Reaplica la geometría al rect actual del editor (resize de ventana),
        sin reanimar y sin interrumpir la animación de entrada."""
        if not self.isVisible():
            return
        if (
            self._animation is not None
            and self._animation.state() == QPropertyAnimation.State.Running
        ):
            return
        height = min(
            max(_MIN_HEIGHT, int(card_rect.height() * _HEIGHT_FRACTION)), card_rect.height()
        )
        bottom = card_rect.y() + card_rect.height()
        self.setGeometry(card_rect.x(), bottom - height, card_rect.width(), height)
        self.raise_()

    def close_sheet(self) -> None:
        # isHidden() (no isVisible()) — el estado propio del widget no depende de
        # que la ventana raíz esté mostrada (evita fugas en tests offscreen).
        if self.isHidden():
            return
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        self.hide()
        self._clear_content()
        self.closed.emit()

    def keyPressEvent(self, event):  # noqa: N802 (Qt API)
        if event.key() == Qt.Key.Key_Escape and self.isVisible():
            self.close_sheet()
            event.accept()
            return
        super().keyPressEvent(event)


__all__ = ["FocoBottomSheet"]
