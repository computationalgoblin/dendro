"""Semillas (Fase A): capa de notificaciones (círculos palpitantes)."""

from __future__ import annotations

import pytest

from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(qapp):
    from PySide6.QtWidgets import QWidget

    p = QWidget()
    p.resize(800, 600)
    yield p  # se mantiene vivo durante el test (si no, Qt lo destruye)
    p.deleteLater()


def test_add_and_remove(parent):
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "Hermano traidor")
    layer.add("c2", "Hermana traidora")
    assert set(layer.notifications) == {"c1", "c2"}
    assert not layer.isHidden()  # mostrada al haber notificaciones
    layer.remove("c1")
    assert set(layer.notifications) == {"c2"}
    layer.clear()
    assert layer.notifications == {}
    assert layer.isHidden()  # oculta al quedar vacía


def test_click_candidate_emits_review_request(parent):
    layer = SeedNotificationLayer(parent)
    seen = []
    layer.reviewRequested.connect(seen.append)
    layer.add("c1", "Algo")
    layer.notifications["c1"].clicked.emit("c1")
    assert seen == ["c1"]


def test_click_error_dismisses_without_review(parent):
    layer = SeedNotificationLayer(parent)
    seen = []
    layer.reviewRequested.connect(seen.append)
    layer.add("error:job1", "Falló", kind="error")
    layer.notifications["error:job1"].clicked.emit("error:job1")
    assert seen == []  # error no abre revisión
    assert "error:job1" not in layer.notifications  # se descarta


def test_anchored_bottom_right(parent):
    layer = SeedNotificationLayer(parent)
    layer.add("c1", "x")
    # Esquina inferior derecha: dentro del padre y pegado al borde.
    assert layer.x() + layer.width() <= parent.width()
    assert layer.y() + layer.height() <= parent.height()
    assert layer.x() > parent.width() // 2
