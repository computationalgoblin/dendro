"""FlowLayout — envuelve sus hijos para que las tarjetas quepan a cualquier ancho."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget  # noqa: E402

from hosts.DesktopHostPySide.widgets.design_system import FlowLayout  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _flow_with_buttons(labels):
    container = QWidget()
    flow = FlowLayout(container)
    btns = [QPushButton(t) for t in labels]
    for b in btns:
        flow.addWidget(b)
    return container, flow, btns


def test_minimum_width_is_far_below_the_row_sum(qapp):
    # El mínimo de la fila NO es la suma de los 4 botones (eso desbordaba): puede
    # encoger muy por debajo, así la tarjeta cabe en paneles estrechos.
    _container, flow, btns = _flow_with_buttons(["Ver", "Revisar", "Aceptar", "Descartar"])
    sum_width = sum(b.sizeHint().width() for b in btns)
    assert flow.minimumSize().width() < sum_width


def test_wraps_to_more_lines_when_narrow(qapp):
    # Estrecho → envuelve a más líneas → más alto que en ancho amplio.
    _container, flow, _btns = _flow_with_buttons(["Ver", "Revisar", "Aceptar", "Descartar"])
    wide = flow.heightForWidth(2000)
    narrow = flow.heightForWidth(60)
    assert narrow > wide


def test_count_and_takeat(qapp):
    _container, flow, _btns = _flow_with_buttons(["A", "B", "C"])
    assert flow.count() == 3
    flow.takeAt(0)
    assert flow.count() == 2
