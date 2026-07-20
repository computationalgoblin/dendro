"""BETA2-FOCO-34 — el riego vuelve a ofrecerse (badge 💧 persistente) y avisa para
revisar en Cultivo tras regar.

Prueba directa de ``SeedNotificationLayer`` (badge adaptativo + aviso «cultivo») y
comprobación del cableado del workspace + la API de FocoView.
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
    from PySide6.QtWidgets import QApplication, QWidget

    from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _layer():
    parent = QWidget()
    parent.resize(400, 300)
    layer = SeedNotificationLayer(parent)
    layer._keepalive_parent = parent  # evita que el QWidget padre lo recoja el GC
    return layer


class TestWaterBadgePersists:
    def test_thirsty_shows_por_regar(self, qapp):
        layer = _layer()
        layer.set_waterable(["a", "b"], ["a", "b", "c"])
        assert not layer._water_badge.isHidden()
        assert "por regar" in layer._water_badge.text()

    def test_only_regada_shows_regar_de_nuevo(self, qapp):
        layer = _layer()
        layer.set_waterable([], ["a", "b", "c"])  # nada sediento, 3 regadas
        assert not layer._water_badge.isHidden()
        assert "Regar de nuevo" in layer._water_badge.text()
        assert "3" in layer._water_badge.text()

    def test_nothing_waterable_hides_badge(self, qapp):
        layer = _layer()
        layer.set_waterable([], [])
        assert layer._water_badge.isHidden()

    def test_water_all_emits_thirsty_first_else_waterable(self, qapp):
        layer = _layer()
        emitted = []
        layer.waterAllRequested.connect(emitted.append)
        layer.set_waterable([], ["x", "y"])
        layer._on_water_clicked()
        assert emitted[-1] == ["x", "y"]


class TestCultivoAviso:
    def test_cultivo_avisos_aggregate_in_one_badge(self, qapp):
        # BETA2-FOCO-36: N avisos → UN badge con contador (no N dots).
        layer = _layer()
        layer.add("ent1", "A — revisar", kind="cultivo")
        layer.add("ent2", "B — revisar", kind="cultivo")
        assert layer.has("ent1") and layer.has("ent2")
        assert not layer._cultivo_badge.isHidden()
        assert "2" in layer._cultivo_badge.text()
        # No infla el badge 🌱 de semillas (solo cuentan los candidatos).
        assert layer._count_badge.isHidden()

    def test_click_cultivo_badge_reviews_oldest_and_decrements(self, qapp):
        layer = _layer()
        seen = []
        layer.cultivoReviewRequested.connect(seen.append)
        layer.add("ent1", "x", kind="cultivo")
        layer.add("ent2", "y", kind="cultivo")
        layer._on_cultivo_clicked()
        assert seen == ["ent1"]  # el más antiguo
        assert not layer.has("ent1") and layer.has("ent2")
        assert "1" in layer._cultivo_badge.text()  # contador decrementado

    def test_water_badge_routes_progress_during_batch(self, qapp):
        # BETA2-FOCO-35: durante el lote, el clic del badge pide el popover de
        # progreso en vez de lanzar otro riego.
        layer = _layer()
        progress = []
        water_all = []
        layer.waterProgressRequested.connect(lambda: progress.append(True))
        layer.waterAllRequested.connect(water_all.append)
        layer.set_watering_progress(1, 9)  # lote en curso
        layer._on_water_clicked()
        assert progress == [True] and water_all == []
        layer.set_watering_progress(0, 0)  # lote terminado
        layer.set_waterable([], ["a"])
        layer._on_water_clicked()
        assert water_all == [["a"]]  # ya no en lote → regar


class TestWiring:
    def test_focoview_exposes_open_cultivo_tab(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        assert callable(getattr(FocoView, "open_cultivo_tab", None))

    def test_workspace_wires_cultivo_review_and_waterable(self, qapp):
        src = Path(__file__).resolve().parents[2] / "hosts/DesktopHostPySide/views/workspaces.py"
        text = src.read_text(encoding="utf-8")
        assert "cultivoReviewRequested.connect(self._on_cultivo_review)" in text
        assert 'kind="cultivo"' in text
        assert "layer.set_waterable(" in text
        assert "open_cultivo_tab" in text
