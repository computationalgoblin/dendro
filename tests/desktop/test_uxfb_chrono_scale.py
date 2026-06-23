"""Cronología proporcional con tope (feedback post-UX10, item 5).

La escala año→y es proporcional a los años (una era de 200 años ≈ 10× una de
20), con un tope generoso para que eras enormes no rompan la navegación, y un
mínimo para separar eventos casi coetáneos.
"""
from __future__ import annotations

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    MAX_GAP_PX,
    MIN_GAP_PX,
    PX_PER_YEAR,
    YearScale,
)


def test_eras_proporcionales_entre_si() -> None:
    scale = YearScale([0, 20, 220])  # tramo de 20 años y tramo de 200 años
    corto = scale.y(20) - scale.y(0)
    largo = scale.y(220) - scale.y(20)
    # 200 años deben ser ~10× los 20 años (ambos por debajo del tope).
    assert abs(largo / corto - 10.0) < 0.6


def test_tope_limita_eras_enormes() -> None:
    scale = YearScale([0, 5000])  # era inmensa
    gap = scale.y(5000) - scale.y(0)
    assert gap == MAX_GAP_PX  # capada, no 5000*PX_PER_YEAR


def test_minimo_separa_eventos_coetaneos() -> None:
    scale = YearScale([0, 1])  # un año de diferencia
    gap = scale.y(1) - scale.y(0)
    assert gap == MIN_GAP_PX  # 1*PX_PER_YEAR sería < MIN, se eleva al mínimo


def test_proporcion_estricta_bajo_el_tope() -> None:
    scale = YearScale([0, 100])
    assert abs((scale.y(100) - scale.y(0)) - 100 * PX_PER_YEAR) < 0.01
