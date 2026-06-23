"""Sistema de iconografía SVG propia (BETA1-UX02).

Verifica que el set de iconos existe, que cada uno se rinde a un QIcon/QPixmap
no vacío, que el tintado colorea de verdad y que un nombre inexistente falla
en silencio (pixmap transparente, sin excepción).
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QGuiApplication

from hosts.DesktopHostPySide.widgets import icons

# Set semántico mínimo que la app debe cubrir (incluye glifos antiguos + extras).
NOMBRES_ESPERADOS = {
    "settings", "project", "creation", "worldbuilding", "search", "filter",
    "save", "back", "close", "chronology", "music", "layers", "expand",
    "collapse", "add", "edit", "delete", "refresh", "gallery", "session",
}


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def test_estan_todos_los_iconos_esperados() -> None:
    disponibles = set(icons.available())
    faltan = NOMBRES_ESPERADOS - disponibles
    assert not faltan, f"faltan SVGs: {sorted(faltan)}"


@pytest.mark.parametrize("name", sorted(NOMBRES_ESPERADOS))
def test_cada_icono_se_rinde_no_vacio(name: str) -> None:
    px = icons.pixmap(name, size=24, color="#45402E")
    assert not px.isNull()
    img = px.toImage()
    opacos = [
        (x, y)
        for x in range(img.width())
        for y in range(img.height())
        if img.pixelColor(x, y).alpha() > 0
    ]
    assert opacos, f"el icono {name!r} salió vacío"
    # Anti-clipping: el icono ocupa el lienzo, no solo el cuadrante superior
    # izquierdo (regresión del bug de devicePixelRatio).
    max_x = max(x for x, _ in opacos)
    max_y = max(y for _, y in opacos)
    assert max_x > img.width() * 0.55, f"{name!r} recortado en X"
    assert max_y > img.height() * 0.55, f"{name!r} recortado en Y"


def test_tintado_aplica_color() -> None:
    px = icons.pixmap("close", size=24, color="#8B7A36")  # GOLD
    img = px.toImage()
    colores = [
        img.pixelColor(x, y)
        for x in range(img.width())
        for y in range(img.height())
        if img.pixelColor(x, y).alpha() > 200
    ]
    assert colores, "no hay píxeles opacos que comprobar"
    # Los píxeles opacos deben ser oro, no el color original del SVG.
    objetivo = QColor("#8B7A36")
    assert any(
        abs(c.red() - objetivo.red()) < 24 and abs(c.green() - objetivo.green()) < 24
        for c in colores
    )


def test_nombre_inexistente_no_rompe() -> None:
    px = icons.pixmap("no_existe_xyz", size=24)
    assert not px.isNull()  # pixmap transparente del tamaño pedido
    assert px.toImage().pixelColor(12, 12).alpha() == 0
