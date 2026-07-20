"""Cuaderno de cultivo: estado, siguiente paso e historial íntegro (BETA2-FOCO-26)."""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


_LONG_SUMMARY = (
    "Informe extenso del riego: la entidad muestra raíces débiles porque sus causas "
    "no están contadas; conviene arraigarla en la metafísica del mundo y ligarla a "
    "los hitos fundacionales que explican su presente narrativo." * 2
)


def _diagnostic(entity_id, scores, *, summary=_LONG_SUMMARY, error=""):
    return SimpleNamespace(
        id="diag-1",
        entity_id=entity_id,
        created_at=datetime(2026, 7, 5, 10, 0, 0),
        scores=dict(scores),
        summary=summary,
        metric_explanations={"arraigo": "Sus causas no están contadas."},
        risks=["Contradicción con la era fundacional"],
        origin="single",
        cost_class="bajo",
        error=error,
    )


class FakeWateringService:
    def __init__(self, status, latest=None, history=None, *, stale=False):
        self._report = SimpleNamespace(
            status=status, latest=latest, stale=stale, last_error=""
        )
        self._history = list(history or [])

    def status_of(self, entity_id):
        return SimpleNamespace(value=self._report)

    def history_for(self, entity_id):
        return SimpleNamespace(value=list(self._history))


def _notebook(service):
    from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import (
        CultivationNotebook,
    )

    notebook = CultivationNotebook(service)
    notebook.set_entity("e1")
    return notebook


class TestRecorridoObservations:
    """PLAY-18: sección «Observaciones del recorrido» alimentada del historial."""

    def _obs(self, text):
        return SimpleNamespace(
            timestamp="2026-07-07T10:00:00", reason=text, description=text
        )

    def test_section_shows_observations_when_present(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import (
            CultivationNotebook,
        )

        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        service = FakeWateringService("regada", latest=latest)
        obs = [self._obs("La Purga golpea a la casa."), self._obs("Duda causal sin resolver.")]
        notebook = CultivationNotebook(service, history_provider=lambda eid: obs)
        notebook.set_entity("e1")

        assert not notebook.obs_toggle.isHidden()
        assert "(2)" in notebook.obs_toggle.text()
        notebook.obs_toggle.setChecked(True)  # desplegar
        from PySide6.QtWidgets import QLabel

        texts = [w.text() for w in notebook.obs_body.findChildren(QLabel)]
        assert any("La Purga golpea" in t for t in texts)

    def test_section_hidden_without_observations(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import (
            CultivationNotebook,
        )

        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = CultivationNotebook(
            FakeWateringService("regada", latest=latest), history_provider=lambda eid: []
        )
        notebook.set_entity("e1")

        assert notebook.obs_toggle.isHidden()

    def test_constructor_without_history_provider_still_works(self, qapp):
        # Compat: el constructor posicional existente sigue válido.
        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = _notebook(FakeWateringService("regada", latest=latest))
        assert notebook.obs_toggle.isHidden()


class TestNextStep:
    def test_never_watered_suggests_watering(self, qapp):
        notebook = _notebook(FakeWateringService("falta_regar", latest=None))
        assert notebook._step_action == ("water", "")
        assert "Regar" in notebook.step_button.text()

    def test_weakest_metric_drives_the_cta(self, qapp):
        latest = _diagnostic("e1", {"arraigo": 32, "nutrida": 71, "iluminada": 55})
        notebook = _notebook(FakeWateringService("regada", latest=latest))
        # arraigo (32) < iluminada (55) < umbral 60 ⇒ gana la MÁS débil.
        assert notebook._step_action == ("suggest", "arraigo")
        assert "32" in notebook.step_button.text()
        # El porqué viene de la explicación de la métrica, y los riesgos se ven.
        assert "causas" in notebook.step_reason.text()
        # UI2-15: riesgos como filas [icono alert + texto], sin ⚠ Unicode.
        assert any("Contradicción" in text for text in notebook.risk_texts())
        assert not notebook.risk_box.isHidden()

    def test_healthy_metrics_offer_quality_pass(self, qapp):
        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = _notebook(FakeWateringService("regada", latest=latest))
        assert notebook._step_action == ("suggest", "calidad")

    def test_stale_reading_suggests_rewatering(self, qapp):
        latest = _diagnostic("e1", {"arraigo": 30, "nutrida": 70, "iluminada": 70})
        notebook = _notebook(FakeWateringService("falta_regar", latest=latest, stale=True))
        assert notebook._step_action == ("water", "")

    def test_dried_offers_resume(self, qapp):
        # BETA2-FOCO-37: Regar/Secar/Cultivar viven ahora en la CultivationStrip;
        # el Cuaderno guía la reactivación por su tarjeta «Siguiente paso» (resume).
        latest = _diagnostic("e1", {"arraigo": 30, "nutrida": 70, "iluminada": 70})
        notebook = _notebook(FakeWateringService("secada", latest=latest))
        assert notebook._step_action == ("resume", "")

    def test_step_button_emits_matching_signal(self, qapp):
        latest = _diagnostic("e1", {"arraigo": 32, "nutrida": 71, "iluminada": 70})
        notebook = _notebook(FakeWateringService("regada", latest=latest))
        seen: list[str] = []
        notebook.suggestRequested.connect(seen.append)
        notebook.step_button.click()
        assert seen == ["arraigo"]


class TestReportAndHistory:
    def test_current_report_shows_full_summary(self, qapp):
        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = _notebook(FakeWateringService("regada", latest=latest, history=[latest]))
        # ÍNTEGRO: nada de summary[:60].
        assert notebook.report_label.text() == _LONG_SUMMARY
        # UI2-15: el informe es texto protagonista, visible directo (sin toggle).
        assert not notebook.report_label.isHidden()
        assert not notebook.report_title.isHidden()

    def test_history_entries_show_full_text(self, qapp):
        old = _diagnostic("e1", {"arraigo": 40, "nutrida": 50, "iluminada": 60})
        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = _notebook(
            FakeWateringService("regada", latest=latest, history=[latest, old])
        )
        # UI2-15: toggle plano, plegado por defecto; despliega con chevron.
        assert "Historial de riegos (2)" in notebook.history_toggle.text()
        assert notebook.history_body.isHidden()
        notebook.history_toggle.setChecked(True)
        assert not notebook.history_body.isHidden()
        labels = [
            child.text()
            for child in notebook.history_body.findChildren(type(notebook.report_label))
        ]
        # El texto completo de cada lectura está presente (antes: 60 caracteres).
        assert any(text == _LONG_SUMMARY for text in labels)


class TestEditorTone:
    def test_dried_entity_darkens_center_card(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        project_service = ProjectService()
        project_service.create("Tono")
        entity = NarrativeEntity(name="Seca")
        project_service.active_project.entities.append(entity)
        latest = _diagnostic(entity.id, {"arraigo": 30, "nutrida": 70, "iluminada": 70})
        view = FocoView(
            project_provider=lambda: project_service.active_project,
            watering_service=FakeWateringService("secada", latest=latest),
        )
        view.center_entity(entity.id)
        assert view._center_card.property("wateringState") == "secada"


class TestBarsOneRowPulido03:
    def test_one_bar_per_row_with_drawer_widths(self, qapp):
        from PySide6.QtWidgets import QApplication as _QApp

        latest = _diagnostic(
            "e1", {"arraigo": 30, "nutrida": 70, "iluminada": 70, "relevancia": 90}
        )
        notebook = _notebook(FakeWateringService("regada", latest=latest, stale=True))
        notebook.resize(420, 600)
        notebook.show()
        _QApp.processEvents()
        # PULIDO-03: UNA barra por fila — cada barra en su propia Y, misma X.
        ys = {bar.pos().y() for bar, _ in notebook.bars.values()}
        xs = {bar.pos().x() for bar, _ in notebook.bars.values()}
        assert len(ys) == len(notebook.bars)
        assert len(xs) == 1
        for bar, pct in notebook.bars.values():
            assert bar.height() == 10  # patrón del drawer
            assert pct.minimumWidth() == 56  # cabe «NN% ·ant.»
        notebook.hide()


class TestNoEmojis:
    def test_notebook_and_chip_sources_have_no_emojis(self):
        # UI2-11/15: todos los glifos son SVG teñidos — cero emojis en fuente.
        from pathlib import Path

        for path in (
            "hosts/DesktopHostPySide/widgets/foco/cultivation_notebook.py",
            "hosts/DesktopHostPySide/widgets/foco/next_step_chip.py",
            "hosts/DesktopHostPySide/widgets/foco/cultivation_strip.py",
        ):
            source = Path(path).read_text(encoding="utf-8")
            for emoji in ("🌱", "💧", "⚠"):
                assert emoji not in source, f"{path} contiene {emoji}"

    def test_metric_rows_carry_svg_icons(self, qapp):
        from PySide6.QtWidgets import QLabel

        latest = _diagnostic("e1", {"arraigo": 80, "nutrida": 75, "iluminada": 90})
        notebook = _notebook(FakeWateringService("regada", latest=latest))
        glyphs = [
            child
            for child in notebook.findChildren(QLabel)
            if child.pixmap() is not None and not child.pixmap().isNull()
        ]
        assert len(glyphs) >= 4, "cada métrica debe llevar su icono SVG"
        # BETA2-FOCO-37: Regar/Secar ya no viven en el Cuaderno (están en la franja).
