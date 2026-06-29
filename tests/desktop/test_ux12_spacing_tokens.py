"""Tokens transversales de espaciado e intervalo de animación (BETA1-UX12).

Verifica que la escala 4-pt y la cadencia de animación existen, son coherentes y
están realmente adoptadas por los widgets animados.
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets import design_system as ds


def test_escala_de_espaciado_es_4pt_y_creciente() -> None:
    escala = [ds.SPACE_XS, ds.SPACE_SM, ds.SPACE_MD, ds.SPACE_LG, ds.SPACE_XL, ds.SPACE_2XL]
    # Estrictamente creciente.
    assert escala == sorted(escala)
    assert len(set(escala)) == len(escala)
    # Múltiplos de 4 (escala 4-pt).
    assert all(v % 4 == 0 for v in escala)
    # Anclas concretas que el resto del sistema asume.
    assert ds.SPACE_XS == 4
    assert ds.SPACE_SM == 8
    assert ds.SPACE_LG == 16


def test_tick_interval_existe_y_es_razonable() -> None:
    # ~25 fps: ni tan alto que cueste CPU, ni tan bajo que se vea a saltos.
    assert 16 <= ds.TICK_INTERVAL <= 60


def test_busy_indicator_usa_tick_interval() -> None:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    ind = ds.BusyIndicator()
    assert ind._timer.interval() == ds.TICK_INTERVAL
