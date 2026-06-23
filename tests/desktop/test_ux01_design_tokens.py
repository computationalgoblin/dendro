"""Cimientos del sistema de diseño (BETA1-UX01).

Verifica que los tokens transversales existen y que la sombra cálida
canvas-safe (``paint_soft_shadow``) realmente pinta — sin depender de
``QGraphicsDropShadowEffect`` (prohibido en widgets dinámicos, lección G08).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from hosts.DesktopHostPySide.widgets import design_system as ds


def test_tokens_existen_y_son_coherentes() -> None:
    # Radios: pocos, ordenados de menor a mayor.
    assert ds.RADIUS_SM < ds.RADIUS_MD < ds.RADIUS_LG
    # Movimiento: tres niveles crecientes.
    assert ds.MOTION_FAST < ds.MOTION_BASE < ds.MOTION_SLOW
    # Curvas definidas.
    assert ds.EASING_STD is not None
    assert ds.EASING_ENTER is not None
    assert ds.EASING_EMPHASIS is not None
    # Escala de elevación 0..3, alpha creciente con el nivel.
    alphas = [ds.ELEVATION[n][2] for n in (0, 1, 2, 3)]
    assert alphas == sorted(alphas)
    assert ds.ELEVATION[0][2] == 0  # el nivel 0 no proyecta sombra


def test_paint_soft_shadow_oscurece_pixeles() -> None:
    img = QImage(120, 120, QImage.Format.Format_ARGB32_Premultiplied)
    fondo = QColor(255, 255, 255)
    img.fill(fondo)

    painter = QPainter(img)
    ds.paint_soft_shadow(painter, QRectF(40, 40, 40, 40), radius=ds.RADIUS_MD, level=3)
    painter.end()

    # Bajo el rectángulo (desplazamiento_y positivo) debe haber píxeles más
    # oscuros que el fondo blanco: la sombra se ha pintado.
    centro_inferior = img.pixelColor(60, 86)
    assert centro_inferior.lightness() < fondo.lightness()


def test_paint_soft_shadow_nivel_cero_no_pinta() -> None:
    img = QImage(80, 80, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    ds.paint_soft_shadow(painter, QRectF(20, 20, 40, 40), level=0)
    painter.end()
    # Nivel 0 = sin sombra: el lienzo sigue blanco.
    assert img.pixelColor(40, 40) == QColor(255, 255, 255)
