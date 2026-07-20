"""BETA2-FOCO-39 — el popover de progreso del lote se refresca EN VIVO.

Antes era un snapshot: si el usuario lo dejaba abierto, se quedaba congelado con
el estado del clic. Ahora ``update_progress`` actualiza título + filas en sitio, y
el workspace lo llama en cada paso del worker mientras siga visible.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.foco.watering_progress_popover import (
        WateringProgressPopover,
    )


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _rows(popover):
    # Filas montadas en la columna del scroll (sin contar el stretch final).
    return popover._col.count() - 1


def test_initial_state_title_and_rows(qapp):
    entries = [{"name": "Aria", "status": "pending", "summary": ""}]
    pop = WateringProgressPopover(entries, 0, 2)
    assert "en curso" in pop._title.text()
    assert "0/2" in pop._title.text()
    assert _rows(pop) == 1
    pop.deleteLater()


def test_update_progress_refreshes_title_and_rows_in_place(qapp):
    pop = WateringProgressPopover(
        [{"name": "Aria", "status": "pending", "summary": ""}], 0, 2
    )
    pop.update_progress(
        [
            {"name": "Aria", "status": "done", "summary": "revisada"},
            {"name": "Borg", "status": "watering", "summary": ""},
        ],
        1,
        2,
    )
    assert "1/2" in pop._title.text()
    assert _rows(pop) == 2  # reconstruye las filas en sitio, sin reabrir
    pop.deleteLater()


def test_finished_flag_marks_completed(qapp):
    pop = WateringProgressPopover(
        [{"name": "Aria", "status": "watering", "summary": ""}], 0, 1
    )
    pop.update_progress(
        [{"name": "Aria", "status": "done", "summary": "ok"}], 1, 1, finished=True
    )
    assert "completado" in pop._title.text()
    assert "1/1" in pop._title.text()
    pop.deleteLater()


def test_workspace_refreshes_live_popover_from_slots(qapp):
    # El workspace refresca el popover vivo en los slots del worker (no snapshot).
    src = Path(__file__).resolve().parents[2] / "hosts/DesktopHostPySide/views/workspaces.py"
    text = src.read_text(encoding="utf-8")
    assert "def _refresh_watering_progress_popover(" in text
    # Se llama desde started / done / progress y en el cierre (finished=True).
    assert text.count("self._refresh_watering_progress_popover(") >= 4
    assert "finished=True" in text
