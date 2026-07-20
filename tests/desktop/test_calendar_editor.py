"""BETA2-CAL-04/06 — CalendarEditor: editor visual del calendario unificado.

Verifica el contrato ``value()``/``set_value()`` (eras encadenadas, presente,
degradación a "solo eras", día de la semana real), la ausencia de QGraphicsEffects en
las rejillas, y la integración con la timeline visual (``EraTimelineBand``): arrastre de
frontera reflejado en ``value()`` y arrastre del presente.
"""

from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication, QGraphicsEffect

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.calendar_editor import CalendarEditor
    from hosts.DesktopHostPySide.widgets.design_system import DisclosureSection


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_editor_starts_with_single_era(qapp):
    editor = CalendarEditor()
    value = editor.value()
    assert len(value["eras"]) == 1
    assert value["present"]["era_index"] == 0


def test_editor_chains_two_eras(qapp):
    editor = CalendarEditor()
    editor.set_value(
        {
            "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
            "present": {"era_index": 1, "year_within": 10},
        }
    )
    value = editor.value()
    assert [(e["name"], e["duration"]) for e in value["eras"]] == [("Era A", 100), ("Era B", 50)]
    assert value["present"]["era_index"] == 1
    assert value["present"]["year_within"] == 10
    # La timeline encadena: Era A empieza en 0, Era B empieza en 100.
    assert editor.timeline._era_start(0) == 0
    assert editor.timeline._era_start(1) == 100


def test_editor_present_year_clamped_to_closed_era_duration(qapp):
    editor = CalendarEditor()
    editor.set_value(
        {
            "eras": [{"name": "Corta", "duration": 5}, {"name": "Abierta", "duration": 10}],
            "present": {"era_index": 0, "year_within": 3},
        }
    )
    # Era cerrada [0,4] → el spin del año presente se limita a 5.
    assert editor.present_year_spin.maximum() == 5


def test_editor_only_eras_hides_month_and_weekday_controls(qapp):
    editor = CalendarEditor()
    editor.set_value(
        {"eras": [{"name": "Sola", "duration": 10}], "present": {"era_index": 0, "year_within": 1}}
    )
    assert editor.present_month_combo.isVisible() is False
    assert editor.weekday_preview.isVisible() is False
    assert editor.value()["months"] == []
    assert editor.value()["weekdays"] == []


def test_editor_previews_real_weekday(qapp):
    editor = CalendarEditor()
    editor.set_value(
        {
            "eras": [{"name": "Primera", "duration": 3}],
            "present": {"era_index": 0, "year_within": 1, "month": "M2", "day": 1},
            "months": [{"name": "M1", "length": 10}, {"name": "M2", "length": 20}],
            "weekdays": ["a", "b", "c", "d", "e", "f", "g"],
            "week_anchor": 0,
        }
    )
    # M2 día 1 = día absoluto 10 → 10 % 7 == 3 → "d".
    assert "d" in editor.weekday_preview.text()


def test_editor_roundtrips_value(qapp):
    payload = {
        "calendar_name": "Calendario",
        "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
        "present": {"era_index": 1, "year_within": 7, "month": "Mes", "day": 2},
        "months": [{"name": "Mes", "length": 12}],
        "weekdays": ["l", "m", "x"],
        "week_anchor": 2,
    }
    editor = CalendarEditor()
    editor.set_value(payload)
    value = editor.value()
    assert value["eras"] == payload["eras"]
    assert value["months"] == payload["months"]
    assert value["weekdays"] == payload["weekdays"]
    assert value["week_anchor"] == 2
    assert value["present"]["era_index"] == 1
    assert value["present"]["year_within"] == 7


def test_editor_keeps_at_least_one_era(qapp):
    editor = CalendarEditor()
    editor.set_value({"eras": [{"name": "Única", "duration": 5}]})
    editor.timeline.remove_era(0)  # no se puede borrar la última
    assert editor.timeline.era_count() == 1
    assert len(editor.value()["eras"]) == 1


def test_editor_boundary_drag_resizes_and_shifts(qapp):
    """Arrastrar la frontera 0 redimensiona Era A; Era B/C conservan su duración."""
    editor = CalendarEditor()
    editor.resize(700, 400)
    editor.set_value(
        {
            "eras": [
                {"name": "A", "duration": 40},
                {"name": "B", "duration": 60},
                {"name": "C", "duration": 100},
            ],
            "present": {"era_index": 0, "year_within": 1},
        }
    )
    editor.timeline.set_boundary_by_drag(0, 70)  # Era A pasa a durar 70 (fin en año 70)
    durations = [e["duration"] for e in editor.value()["eras"]]
    assert durations == [70, 60, 100]


def test_editor_present_drag_updates_present(qapp):
    editor = CalendarEditor()
    editor.resize(700, 400)
    editor.set_value(
        {
            "eras": [{"name": "A", "duration": 40}, {"name": "B", "duration": 100}],
            "present": {"era_index": 0, "year_within": 1},
        }
    )
    editor.timeline.set_present_by_drag(55)  # año 55 → Era B (inicio 40) año 16
    present = editor.value()["present"]
    assert present["era_index"] == 1
    assert present["year_within"] == 16


def test_editor_changed_emits_on_timeline_edit(qapp):
    editor = CalendarEditor()
    editor.resize(700, 400)
    editor.set_value({"eras": [{"name": "A", "duration": 40}, {"name": "B", "duration": 100}]})
    seen = []
    editor.changed.connect(lambda: seen.append(True))
    editor.timeline.add_era("Nueva")
    assert seen, "editar la timeline debe emitir CalendarEditor.changed"
    assert len(editor.value()["eras"]) == 3


def test_disclosure_sections_use_no_graphics_effects(qapp):
    editor = CalendarEditor()
    editor.set_value(
        {
            "eras": [{"name": "E", "duration": 5}],
            "months": [{"name": "M", "length": 10}],
            "weekdays": ["a", "b"],
        }
    )
    sections = editor.findChildren(DisclosureSection)
    assert sections, "deben existir secciones plegables"
    for section in sections:
        assert section.graphicsEffect() is None
        assert section.body.graphicsEffect() is None
    # Ningún efecto gráfico en todo el editor (rejillas dinámicas).
    assert not editor.findChildren(QGraphicsEffect)
