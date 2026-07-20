"""BETA2-CAL-06 — EraTimelineBand: timeline visual de eras encadenadas.

Prueba la lógica pura (escala año↔píxel, arrastre de fronteras redimensiona-y-desplaza,
línea de presente, alta/baja/orden y clamps) llamando a las rutas de edición directas
(mismo patrón que ``test_foco_lifeline.py``): sin sintetizar eventos de ratón.
"""

from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.era_timeline import EraTimelineBand


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _band(qapp, eras=None, present_index=0, year_within=1):
    band = EraTimelineBand()
    band.resize(600, 120)
    if eras is not None:
        band.set_eras(eras, present_index, year_within)
    return band


def test_starts_with_single_open_era(qapp):
    band = _band(qapp)
    assert band.era_count() == 1
    assert band.present() == (0, 1)


def test_set_eras_loads_and_selects_present(qapp):
    band = _band(
        qapp,
        [
            {"name": "A", "duration": 30},
            {"name": "B", "duration": 40},
            {"name": "C", "duration": 100},
        ],
        present_index=1,
        year_within=5,
    )
    assert [e["duration"] for e in band.eras()] == [30, 40, 100]
    assert band.present() == (1, 5)
    assert band._era_start(1) == 30
    assert band._era_start(2) == 70


def test_x_year_roundtrip(qapp):
    band = _band(qapp, [{"name": "A", "duration": 40}, {"name": "B", "duration": 60}])
    for year in (0, 10, 40, 70, 100):
        assert abs(band.year_at(band.x_at(year)) - year) <= 1


def test_boundary_drag_resizes_and_shifts(qapp):
    band = _band(
        qapp,
        [
            {"name": "A", "duration": 40},
            {"name": "B", "duration": 60},
            {"name": "C", "duration": 100},
        ],
    )
    band.set_boundary_by_drag(0, 70)  # Era A termina en el año 70 → dura 70
    assert [e["duration"] for e in band.eras()] == [70, 60, 100]
    # Era B ahora empieza en 70 (se desplazó); su duración no cambió.
    assert band._era_start(1) == 70


def test_boundary_drag_clamps_to_min_one(qapp):
    band = _band(qapp, [{"name": "A", "duration": 40}, {"name": "B", "duration": 60}])
    band.set_boundary_by_drag(0, -5)  # no puede reducir por debajo de 1 año
    assert band.eras()[0]["duration"] == 1


def test_open_extent_drag_sets_last_duration(qapp):
    band = _band(qapp, [{"name": "A", "duration": 40}, {"name": "B", "duration": 100}])
    band.set_open_extent_by_drag(200)  # B empieza en 40 → nueva duración 160
    assert band.eras()[1]["duration"] == 160


def test_present_drag_sets_index_and_year_within(qapp):
    band = _band(qapp, [{"name": "A", "duration": 40}, {"name": "B", "duration": 100}])
    band.set_present_by_drag(55)  # año 55 → Era B (inicio 40) año 16
    assert band.present() == (1, 16)


def test_present_year_within_clamped_in_closed_era(qapp):
    band = _band(
        qapp, [{"name": "A", "duration": 5}, {"name": "B", "duration": 10}], present_index=0
    )
    band.set_present_year_within(99)
    assert band.present() == (0, 5)  # cerrada [0,4] → año dentro ≤ 5


def test_present_year_within_free_in_open_era(qapp):
    band = _band(
        qapp, [{"name": "A", "duration": 5}, {"name": "B", "duration": 10}], present_index=1
    )
    band.set_present_year_within(99)
    assert band.present() == (1, 99)  # la abierta no acota


def test_add_era_appends_and_selects(qapp):
    band = _band(qapp, [{"name": "A", "duration": 40}])
    idx = band.add_era("Nueva")
    assert band.era_count() == 2
    assert idx == band.selected_index() == 1
    assert band.eras()[1]["name"] == "Nueva"


def test_remove_era_keeps_at_least_one(qapp):
    band = _band(qapp, [{"name": "Única", "duration": 5}])
    band.remove_era(0)
    assert band.era_count() == 1


def test_remove_era_adjusts_present_index(qapp):
    band = _band(
        qapp,
        [
            {"name": "A", "duration": 10},
            {"name": "B", "duration": 20},
            {"name": "C", "duration": 30},
        ],
        present_index=2,
    )
    band.remove_era(0)  # se elimina antes del presente → índice baja
    assert band.era_count() == 2
    assert band.present()[0] == 1


def test_move_era_reorders_and_tracks_present(qapp):
    band = _band(
        qapp,
        [{"name": "A", "duration": 10}, {"name": "B", "duration": 20}],
        present_index=0,
    )
    band.move_era(0, +1)  # A y B intercambian; el presente sigue a la era A
    assert [e["name"] for e in band.eras()] == ["B", "A"]
    assert band.present()[0] == 1


def test_changed_not_emitted_during_load_but_on_edit(qapp):
    band = _band(qapp)
    seen = []
    band.changed.connect(lambda: seen.append(True))
    band.set_eras([{"name": "A", "duration": 10}, {"name": "B", "duration": 20}], 0, 1)
    assert seen == []  # set_eras no emite (carga)
    band.set_boundary_by_drag(0, 15)
    assert seen == [True]


def test_paint_offscreen_smoke(qapp):
    band = _band(
        qapp,
        [{"name": "Edad Larga", "duration": 40}, {"name": "Presente", "duration": 100}],
        present_index=1,
        year_within=8,
    )
    band.repaint()  # no debe lanzar en offscreen
