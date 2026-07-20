"""UI2-16: editor de entidad a PANTALLA COMPLETA del Modo Foco.

La tarjeta central es un display de lectura; aquí es donde se ESCRIBE. Overlay
hijo de FocoView que cubre todo el lienzo con un velo pergamino translúcido
(las hojas de la atmósfera siguen vivas y asoman por los márgenes) y centra
una columna editorial (~900px) con cabecera (retrato + nombre + flechas de
navegación + cerrar) y las pestañas Ficha/Relaciones/Cultivo montadas por
FocoView. Esc cierra. Pintura a mano — sin QGraphicsEffect (regla del repo).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_SOFT,
    GOLD_TINT,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    RADIUS_LG,
    SAGE,
    SPACE_LG,
    SPACE_MD,
    SURFACE,
    SURFACE_HI,
    TYPE_H1_PX,
    ElidedLabel,
)

# Ancho máximo de la columna editorial: cómodo para escribir, nunca un muro.
_EDITOR_MAX_WIDTH = 900


class EntityEditorOverlay(QWidget):
    """Velo pergamino + columna editorial centrada; la edición vive aquí."""

    closeRequested = Signal()  # noqa: N815 — convención Qt de señales
    # (tecla Qt, shift) — las flechas de la cabecera navegan sin salir.
    navRequested = Signal(int, bool)  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hide()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.addStretch(1)
        self.editor_card = QFrame(self)
        self.editor_card.setObjectName("focoEditorCard")
        self.editor_card.setProperty("wateringState", "")
        self.editor_card.setMaximumWidth(_EDITOR_MAX_WIDTH)
        self.editor_card.setStyleSheet(
            f"QFrame#focoEditorCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: {RADIUS_LG}px; }} "
            f'QFrame#focoEditorCard[wateringState="secada"] {{ background: #E9E2CE; '
            f"border: 1px solid {LINE_SOFT}; border-radius: {RADIUS_LG}px; }} "
            # UI2-21: regando — tinte SAGE también en el editor a pantalla completa.
            f'QFrame#focoEditorCard[wateringState="regando"] {{ background: #D7E0C8; '
            f"border: 2px solid {SAGE}; border-radius: {RADIUS_LG}px; }}"
        )
        outer.addWidget(self.editor_card, 4)
        outer.addStretch(1)

        column = QVBoxLayout(self.editor_card)
        column.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        column.setSpacing(8)

        # ── Cabecera: retrato mini + nombre + navegación + cerrar ─────────
        header = QHBoxLayout()
        header.setSpacing(10)
        self.portrait_mini = QLabel(self.editor_card)
        self.portrait_mini.setFixedSize(32, 32)
        self.portrait_mini.setScaledContents(True)
        self.portrait_mini.setStyleSheet(
            f"border: 1px solid {LINE_SOFT}; border-radius: 6px; background: transparent;"
        )
        self.portrait_mini.hide()
        header.addWidget(self.portrait_mini)
        self.name_label = ElidedLabel("", self.editor_card)
        self.name_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; "
            f"font-size: {TYPE_H1_PX}px; font-weight: 700; border: none; background: transparent;"
        )
        header.addWidget(self.name_label, 1)

        def _nav_button(icon_name: str, tooltip: str, key: int, shift: bool) -> QToolButton:
            button = QToolButton(self.editor_card)
            button.setIcon(icons.icon(icon_name, color=INK_SOFT, size=15))
            button.setIconSize(QSize(15, 15))
            button.setToolTip(tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(28, 28)
            button.setStyleSheet(
                "QToolButton { border: 1px solid " + LINE_SOFT + "; border-radius: 14px; "
                "background: transparent; } "
                "QToolButton:hover { background: " + GOLD_TINT + "; border-color: "
                + GOLD_SOFT + "; } "
                "QToolButton:disabled { border-color: " + LINE_SOFT + "; }"
            )
            button.clicked.connect(lambda _=False: self.navRequested.emit(key, shift))
            header.addWidget(button)
            return button

        self.nav_left = _nav_button(
            "arrow_left", "Anterior del anillo", int(Qt.Key.Key_Left), False
        )
        self.nav_right = _nav_button(
            "arrow_right", "Siguiente del anillo", int(Qt.Key.Key_Right), False
        )
        self.nav_up = _nav_button(
            "arrow_up", "Subir a la rama contenedora", int(Qt.Key.Key_Up), False
        )
        self.nav_down = _nav_button(
            "arrow_down", "Bajar a los miembros", int(Qt.Key.Key_Down), False
        )
        self.close_button = QToolButton(self.editor_card)
        self.close_button.setIcon(icons.icon("close", color=INK_SOFT, size=15))
        self.close_button.setIconSize(QSize(15, 15))
        self.close_button.setToolTip("Cerrar el editor (Esc)")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setStyleSheet(
            "QToolButton { border: none; border-radius: 14px; background: transparent; } "
            "QToolButton:hover { background: " + GOLD_TINT + "; }"
        )
        self.close_button.clicked.connect(self.closeRequested)
        header.addWidget(self.close_button)
        column.addLayout(header)

        # ── Huecos que FocoView monta (pestañas + stack + pie) ────────────
        self._mount_slot = QVBoxLayout()
        self._mount_slot.setSpacing(8)
        column.addLayout(self._mount_slot, 1)
        self.footer_slot = QVBoxLayout()
        column.addLayout(self.footer_slot)

        # Esc cierra (local al overlay; el dual nunca coexiste con él).
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._esc.activated.connect(self.closeRequested)

    # ── API ────────────────────────────────────────────────────────────────

    def mount(self, tab_bar: QWidget, tab_stack: QWidget) -> None:
        """Adopta las pestañas y el stack de FocoView (una sola vez)."""
        self._mount_slot.addWidget(tab_bar, 0, Qt.AlignmentFlag.AlignLeft)
        self._mount_slot.addWidget(tab_stack, 1)

    def set_header(self, name: str, portrait: QPixmap | None) -> None:
        self.name_label.setText(str(name or ""))
        if portrait is None or portrait.isNull():
            self.portrait_mini.clear()
            self.portrait_mini.hide()
            return
        self.portrait_mini.setPixmap(portrait)
        self.portrait_mini.show()

    def set_nav_enabled(self, prev: bool, next_: bool, up: bool, down: bool) -> None:
        self.nav_left.setEnabled(bool(prev))
        self.nav_right.setEnabled(bool(next_))
        self.nav_up.setEnabled(bool(up))
        self.nav_down.setEnabled(bool(down))

    # ── Pintura: velo pergamino translúcido ────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        veil = QColor(SURFACE)
        veil.setAlphaF(0.86)
        path = QPainterPath()
        path.addRect(0, 0, float(self.width()), float(self.height()))
        painter.fillPath(path, veil)
        painter.end()


__all__ = ["EntityEditorOverlay"]
