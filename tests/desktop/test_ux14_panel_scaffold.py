"""Base común de paneles PanelScaffold (BETA1-UX14)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from hosts.DesktopHostPySide.widgets.design_system import Badge, PanelScaffold, SectionHeader


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_estructura_cabecera_y_cuerpo() -> None:
    panel = PanelScaffold("Título", "Subtítulo")
    assert isinstance(panel.header, SectionHeader)
    # El cuerpo está vacío al inicio y acepta contenido.
    assert panel.body.count() == 0
    panel.add_widget(QPushButton("x"))
    assert panel.body.count() == 1


def test_badge_opcional_en_cabecera() -> None:
    panel = PanelScaffold("T", badge="EDICIÓN", badge_tone="gold")
    badges = panel.findChildren(Badge)
    assert any(b.text() == "EDICIÓN" for b in badges)


def test_sin_badge_no_crea_chip() -> None:
    panel = PanelScaffold("T")
    assert panel.findChildren(Badge) == []


def test_action_bar_idempotente() -> None:
    panel = PanelScaffold("T")
    bar1 = panel.add_action_bar()
    bar2 = panel.add_action_bar()
    assert bar1 is bar2  # no duplica la fila de acciones


def test_panel_base_adopta_scaffold() -> None:
    # Las subclases de settings deben seguir montando sobre self.layout (= body).
    from hosts.DesktopHostPySide.widgets.settings_panels import _PanelBase

    panel = _PanelBase("Proyecto", "sub")
    assert panel.layout is panel.body
    panel.layout.addWidget(QPushButton("ok"))
    assert panel.body.count() == 1
