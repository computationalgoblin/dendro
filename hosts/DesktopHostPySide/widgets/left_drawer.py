"""LeftDrawer — cajón deslizante izquierdo (B31 immersive UX).

Espejo de `RightDrawer` que entra desde la IZQUIERDA. Usado para el panel de
Configuración / Ajustes IA. La mecánica vive en `BaseSlideDrawer`; aquí solo el
estilo del lado izquierdo. (Antes era una copia manual de RightDrawer que se
desincronizaba: no animaba el suelo de ancho al cerrar y se descolocaba.)
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets.base_slide_drawer import BaseSlideDrawer


class LeftDrawer(BaseSlideDrawer):
    """Cajón izquierdo. Usado para ConfigPanel (configuración/ajustes).

    Usage:
        drawer = LeftDrawer(parent)
        drawer.set_content(my_widget, title="...")
        drawer.open()
        drawer.close()
    """

    OBJECT_NAME = "leftDrawer"
    ANCHOR = "left"  # overlay: crece desde el borde izquierdo del área del grafo
    # BETA1-UX: mínimo amplio para que la configuración no se corte.
    WIDTH_FRACTION = 0.42
    WIDTH_MIN = 480
    WIDTH_MAX = 640
    HEADER_HEIGHT = 44
    HEADER_MARGINS = (14, 6, 14, 6)
    CLOSE_ICON_COLOR = "#6F6A42"
    CLOSE_ICON_SIZE = 14

    def _frame_style(self) -> str:
        # BETA1-UX07: lomo dorado coherente con el cajón derecho.
        return (
            "QFrame#leftDrawer { "
            "background: #F8F6ED; "
            "border-right: 3px solid #BBAA66; "
            "border-radius: 0px; "
            "}"
        )

    def _header_style(self) -> str:
        return "background: #EEECDD; border-bottom: 1px solid #D8D6C8;"

    def _title_style(self) -> str:
        return (
            "font-size: 14px; font-weight: 700; color: #5C5A3E; "
            "background: transparent; border: none;"
        )

    def _close_btn_style(self) -> str:
        return (
            "QPushButton { background: transparent; border: 1px solid #D0CCB8; "
            "border-radius: 9px; } "
            "QPushButton:hover { background: #F8F5EA; }"
        )

    def _scroll_style(self) -> str:
        return "background: transparent;"
