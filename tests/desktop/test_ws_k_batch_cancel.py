"""BETA-CIERRE WS-K: el popover de progreso del riego puede CANCELAR el lote.

La maquinaria de cancelación existía (WateringBatchWorker.request_cancel +
_cancel_watering_batch) pero estaba desconectada de la única superficie viva del lote:
el popover «Regando x/y». Sin botón, un lote grande gastaba API sin poder pararse.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.foco.watering_progress_popover import (  # noqa: E402
    WateringProgressPopover,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_cancel_button_toggles_and_emits(app):
    entries = [{"name": "A", "status": "watering", "summary": ""}]
    pop = WateringProgressPopover(entries, 0, 2)

    assert not pop._cancel_btn.isHidden()  # visible mientras el lote corre

    fired = []
    pop.cancelRequested.connect(lambda: fired.append(True))
    pop._cancel_btn.click()
    assert fired == [True]  # el botón corta el lote

    pop.update_progress(entries, 2, 2, finished=True)
    assert pop._cancel_btn.isHidden()  # oculto cuando el lote termina
