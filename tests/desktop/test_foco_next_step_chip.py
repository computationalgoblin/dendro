"""Chip «siguiente paso» de la cabecera de Foco (BETA2-JARDIN-04)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.watering_guidance import NextStep  # noqa: E402 — guard HAS_QT


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _chip(qapp):
    from hosts.DesktopHostPySide.widgets.foco.next_step_chip import NextStepChip

    return NextStepChip()


class TestNextStepChip:
    def test_hidden_without_urgent_step(self, qapp):
        chip = _chip(qapp)
        assert chip.isHidden()
        chip.set_step(NextStep(kind="water"))
        assert not chip.isHidden()
        # Sano (polish), secada (resume) o sin reporte → el chip desaparece.
        for step in (NextStep(kind="polish"), NextStep(kind="resume"), None):
            chip.set_step(step)
            assert chip.isHidden()

    def test_water_step_emits_water(self, qapp):
        chip = _chip(qapp)
        seen: list[str] = []
        chip.waterClicked.connect(lambda: seen.append("water"))
        chip.set_step(NextStep(kind="water"))
        assert "Regar ahora" in chip.text()
        chip.click()
        assert seen == ["water"]

    def test_suggest_step_emits_metric(self, qapp):
        chip = _chip(qapp)
        seen: list[str] = []
        chip.suggestClicked.connect(seen.append)
        chip.set_step(
            NextStep(kind="suggest", metric="nutrida", score=40, reason="Poco contenido.")
        )
        assert "Nutrida débil (40)" in chip.text()
        assert chip.toolTip() == "Poco contenido."
        chip.click()
        assert seen == ["nutrida"]

    def test_stale_step_replaced_cleanly(self, qapp):
        chip = _chip(qapp)
        chip.set_step(NextStep(kind="suggest", metric="arraigo", score=10))
        chip.set_step(NextStep(kind="water"))
        chip_seen: list[str] = []
        chip.suggestClicked.connect(chip_seen.append)
        chip.click()  # ahora es water: no debe emitir sugerencia vieja
        assert chip_seen == []


class TestChipDiscipline:
    """PULIDO-03: el chip jamás fuerza el layout ni duplica al Cuaderno."""

    def test_chip_width_is_bounded_even_with_long_reason(self, qapp):
        chip = _chip(qapp)
        chip.set_step(
            NextStep(kind="suggest", metric="iluminada", score=45, reason="x" * 300)
        )
        assert chip.maximumWidth() == chip.MAX_WIDTH
        assert chip.sizeHint().width() <= chip.MAX_WIDTH

    def test_hover_uses_background_grammar(self, qapp):
        chip = _chip(qapp)
        style = chip.styleSheet()
        assert ":hover" in style
        assert "background: #BBAA66" in style  # GOLD_SOFT: hover por fondo

    def test_no_emojis_only_svg_icons(self, qapp):
        # UI2-11: todos los glifos de la app son SVG teñidos, nunca emojis
        # (patrón del badge de riego, test_seed_notifications).
        from packages.application.watering_guidance import NextStep

        chip = _chip(qapp)
        chip.set_step(NextStep(kind="water"))
        assert "💧" not in chip.text()
        assert not chip.icon().isNull()
        chip.set_step(NextStep(kind="suggest", metric="nutrida", score=40, reason="x"))
        assert "🌱" not in chip.text()
        assert not chip.icon().isNull()


class TestSourceWiring:
    def test_foco_view_mounts_and_refreshes_the_strip(self):
        # BETA2-FOCO-37: la franja lleva los iconos Regar/Secar/Cultivar; el chip
        # verboso se retiró. «Sugerir X» vive en el Cuaderno.
        source = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(
            encoding="utf-8"
        )
        assert "self.cultivation_strip = CultivationStrip(card)" in source
        assert "def _refresh_next_step_chip" in source
        assert "self.cultivation_strip.waterClicked.connect" in source
        assert "NextStepChip" not in source  # ya no se usa en la vista

    def test_strip_hides_only_in_cultivo_tab(self):
        # UI2-16: la franja vive en la tarjeta de lectura o el pie del editor;
        # SOLO se oculta con el editor abierto en la pestaña Cultivo (ahí manda el
        # Cuaderno). La regla sigue en _refresh_next_step_chip (único punto de verdad).
        source = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(
            encoding="utf-8"
        )
        assert 'if self._editor_open and self._tab_bar.current() == "cultivo":' in source
        assert "strip.hide()" in source
        assert "strip.set_report(report, is_ghost=is_ghost)" in source

    def test_threshold_single_source_of_truth(self):
        # El 60 vive SOLO en watering_guidance; drawer y Cuaderno lo importan.
        for path in (
            "hosts/DesktopHostPySide/widgets/foco/watering_panel.py",
            "hosts/DesktopHostPySide/widgets/foco/cultivation_notebook.py",
        ):
            source = Path(path).read_text(encoding="utf-8")
            assert "WEAK_THRESHOLD = 60" not in source
            assert "watering_guidance import" in source
