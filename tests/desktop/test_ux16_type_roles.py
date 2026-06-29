"""Roles tipográficos nombrados (BETA1-UX16)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets import design_system as ds


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_escala_tipografica_coherente() -> None:
    assert ds.TYPE_H1_PX > ds.TYPE_H2_PX > ds.TYPE_BODY_PX > ds.TYPE_CAPTION_PX
    assert ds.TYPE_BODY_PX == 13
    assert ds.TYPE_H1_PX == 19


def test_role_font_aplica_tamano_y_peso() -> None:
    h1 = ds.role_font("h1")
    assert h1.pixelSize() == ds.TYPE_H1_PX
    assert h1.weight() == ds.role_font("h1").weight()
    body = ds.role_font("body")
    assert body.pixelSize() == ds.TYPE_BODY_PX
    # Rol desconocido degrada a body.
    assert ds.role_font("zzz").pixelSize() == ds.TYPE_BODY_PX


def test_role_font_familia_serif_vs_sans() -> None:
    assert ds.role_font("body", serif=True).family() == "Georgia"
    assert ds.role_font("label", serif=False).family() == "Segoe UI"


def test_familias_definidas() -> None:
    assert "Georgia" in ds.FONT_SERIF
    assert "Segoe UI" in ds.FONT_SANS
