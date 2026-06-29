"""RightDrawer — cajón deslizante derecho (B31 immersive UX).

Sustituye la edición por QDialog con un panel que entra desde la derecha dentro
de la ventana principal. La mecánica (animación, abrir/cerrar, limpieza de
contenido) vive en `BaseSlideDrawer`; aquí solo el estilo del lado derecho.
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets.base_slide_drawer import BaseSlideDrawer
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_SOFT,
    INK_SOFT,
    INK_STRONG,
    LINE,
    LINE_STRONG,
    SURFACE,
    SURFACE_HI,
)


class RightDrawer(BaseSlideDrawer):
    """Cajón derecho. Usado para el panel de Proyecto y paneles de detalle.

    Usage:
        drawer = RightDrawer(parent)
        drawer.set_content(my_widget, title="...")
        drawer.open()
        drawer.close()
    """

    OBJECT_NAME = "rightDrawer"
    ANCHOR = "right"  # overlay: crece desde el borde derecho del área del grafo
    # BETA1-UX feedback: mínimo MÁS amplio (520) para que el contenido de
    # configuración —cronología/calendario incluidos— quepa siempre sin cortarse
    # a la derecha, incluso en la ventana más estrecha.
    WIDTH_FRACTION = 0.44
    WIDTH_MIN = 520
    WIDTH_MAX = 680
    HEADER_HEIGHT = 48
    HEADER_MARGINS = (16, 7, 12, 7)
    CLOSE_ICON_COLOR = INK_SOFT
    CLOSE_ICON_SIZE = 13

    def _frame_style(self) -> str:
        # BETA1-UX07: lomo dorado fino que ata el cajón al mundo cálido (deja de
        # ser una hoja de formulario blanca con un borde gris).
        return (
            f"QFrame#rightDrawer {{ "
            f"background: {SURFACE}; "
            f"border-left: 3px solid {GOLD_SOFT}; "
            f"border-radius: 0px; "
            f"}}"
        )

    def _header_style(self) -> str:
        return (
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {SURFACE_HI}, stop:1 {SURFACE}); "
            f"border-bottom: 1px solid {LINE_STRONG};"
        )

    def _title_style(self) -> str:
        return (
            f"font-size: 15px; font-weight: 700; color: {INK_STRONG}; "
            f"letter-spacing: 0.3px; background: transparent; border: none;"
        )

    def _close_btn_style(self) -> str:
        return (
            f"QPushButton {{ background: transparent; border: 1px solid {LINE}; "
            f"border-radius: 15px; }} "
            f"QPushButton:hover {{ background: {SURFACE}; border-color: {GOLD}; }}"
        )

    def _scroll_style(self) -> str:
        return (
            f"QScrollArea {{ background: {SURFACE}; border: none; }} "
            f"QScrollArea > QWidget > QWidget {{ background: {SURFACE}; }}"
        )

    def _viewport_style(self) -> str:
        return f"background: {SURFACE};"
