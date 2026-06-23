"""Iconografía SVG propia de Dendro (BETA1-UX02).

Set de iconos de línea con identidad botánica/editorial, recoloreables a
cualquier tono de la paleta. Sustituye a los glifos/emoji Unicode (que
dependían de fuentes del sistema y rompían la paleta: 🌐 azul, ⚙ de color).

Los SVG viven en ``hosts/DesktopHostPySide/assets/icons/<nombre>.svg`` y se
tiñen en tiempo de carga (``CompositionMode_SourceIn``), de modo que el color
del archivo es irrelevante: el llamante pide el tono. Presentation-only.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from hosts.DesktopHostPySide.widgets.design_system import INK_SOFT

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
_RENDER_SCALE = 2  # render a 2x para nitidez en pantallas HiDPI

# Nombres semánticos disponibles (un SVG por nombre). Alias para compatibilidad
# con vocabularios previos (p. ej. la cronología o el filtro del canvas).
_ALIASES = {
    "clock": "chronology",
    "time": "chronology",
    "download": "save",
    "globe": "worldbuilding",
    "rings": "worldbuilding",
}


def available() -> list[str]:
    """Nombres de iconos con SVG en disco (sin extensión)."""
    try:
        return sorted(p.stem for p in _ICONS_DIR.glob("*.svg"))
    except OSError:
        return []


@lru_cache(maxsize=256)
def _svg_data(name: str) -> bytes | None:
    resolved = _ALIASES.get(name, name)
    path = _ICONS_DIR / f"{resolved}.svg"
    try:
        return path.read_bytes()
    except OSError:
        return None


def pixmap(name: str, *, size: int = 20, color: str | None = INK_SOFT) -> QPixmap:
    """Devuelve un QPixmap del icono *name*, teñido a *color* (hex) si se indica.

    Si el icono no existe, devuelve un pixmap transparente del tamaño pedido
    (falla en silencio para no romper la UI).
    """
    dim = int(size * _RENDER_SCALE)
    px = QPixmap(dim, dim)
    px.fill(Qt.GlobalColor.transparent)
    data = _svg_data(name)
    if data:
        try:
            renderer = QSvgRenderer(QByteArray(data))
            painter = QPainter(px)
            # Pintamos en píxeles FÍSICOS (DPR=1); el viewBox 24x24 del SVG se
            # escala para llenar el rect completo. La nitidez HiDPI se aplica al
            # final con setDevicePixelRatio (patrón estándar de Qt).
            renderer.render(painter, QRectF(0, 0, dim, dim))
            if color:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(px.rect(), QColor(color))
            painter.end()
        except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
            pass
    px.setDevicePixelRatio(_RENDER_SCALE)
    return px


def icon(name: str, *, color: str | None = INK_SOFT, size: int = 20) -> QIcon:
    """Devuelve un QIcon del icono *name*, teñido a *color*."""
    return QIcon(pixmap(name, size=size, color=color))


def set_button_icon(button, name: str, *, color: str | None = INK_SOFT, size: int = 18) -> None:
    """Pone el icono SVG *name* en un QAbstractButton y limpia su texto.

    Conveniencia para migrar botones que mostraban un glifo Unicode como texto.
    Falla en silencio si el botón no admite icono.
    """
    try:
        button.setIcon(icon(name, color=color, size=size))
        button.setIconSize(QSize(size, size))
        button.setText("")
    except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
        pass
