"""BETA-MULTIAGENT2-FIX-09 (G2-15): el hilo causal en el panel de detalle del hito.

Lo único que la app enseñaba del hilo era un contador («Consecuencias (hitos
posteriores): 2») que no decía cuáles, no era clicable y no permitía crear ni
quitar el enlace. Y el rótulo de los padres decía lo CONTRARIO del dato.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.persistence.store import ProjectStore  # noqa: E402

if HAS_QT:
    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )
    from hosts.DesktopHostPySide.widgets.loose_threads_panel import LooseThreadsPanel
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _panel_for(ctrl, ps, milestone_id, **kwargs):
    ctx = SimpleNamespace(
        log=lambda *a, **k: None, notify=lambda *a, **k: None, drawer=None
    )
    return MilestoneDetailPanel(
        ctx, ctrl, milestone_id, project_getter=lambda: ps.active_project, **kwargs
    )


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="Hilo")
    ctrl = CausalMilestoneController(ps)
    setup = ctrl.create_manual({"title": "1x03 — Caja negra", "year": 3}).value
    payoff = ctrl.create_manual({"title": "2x03 — La caja habla", "year": 20}).value
    return ps, ctrl, setup, payoff


class TestHiloCausalEnElPanel:
    def test_lista_padres_e_hijos_por_nombre(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)

        panel = _panel_for(ctrl, ps, setup.id)
        efectos = [
            panel.effects_list.item(i).text() for i in range(panel.effects_list.count())
        ]
        assert any("2x03 — La caja habla" in t for t in efectos)

        panel_hijo = _panel_for(ctrl, ps, payoff.id)
        causas = [
            panel_hijo.causes_list.item(i).text()
            for i in range(panel_hijo.causes_list.count())
        ]
        assert any("1x03 — Caja negra" in t for t in causas)

    def test_vincular_consecuencia_llama_al_controller_y_se_ve_en_ambos(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        panel = _panel_for(ctrl, ps, setup.id)
        idx = next(
            i
            for i in range(panel.link_effect_combo.count())
            if panel.link_effect_combo.itemData(i) == payoff.id
        )
        panel.link_effect_combo.setCurrentIndex(idx)
        panel._link_effect()

        # canon: el hijo declara su causa y el padre conoce su consecuencia
        assert payoff.causal_parent_hito_ids == [setup.id]
        assert setup.causal_child_hito_ids == [payoff.id]
        # y tras recargar el panel el enlace se ve en LOS DOS hitos
        assert panel.effects_list.count() == 1
        otro = _panel_for(ctrl, ps, payoff.id)
        assert otro.causes_list.count() == 1

    def test_vincular_causa_desde_el_payoff(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        panel = _panel_for(ctrl, ps, payoff.id)
        idx = next(
            i
            for i in range(panel.link_cause_combo.count())
            if panel.link_cause_combo.itemData(i) == setup.id
        )
        panel.link_cause_combo.setCurrentIndex(idx)
        panel._link_cause()

        assert payoff.causal_parent_hito_ids == [setup.id]

    def test_quitar_el_enlace_desde_el_panel(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)
        panel = _panel_for(ctrl, ps, setup.id)
        panel.effects_list.setCurrentRow(0)
        panel._remove_selected_effect()

        assert payoff.causal_parent_hito_ids == []
        assert setup.causal_child_hito_ids == []
        assert panel.effects_list.count() == 1  # el aviso de «nadie lo recoge»
        assert "Nadie recoge" in panel.effects_list.item(0).text()

    def test_doble_clic_abre_el_hito_enlazado(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)
        abiertos: list[str] = []
        panel = _panel_for(ctrl, ps, setup.id, on_open_milestone=abiertos.append)
        panel._open_selected_causal(panel.effects_list.item(0))
        assert abiertos == [payoff.id]

    def test_el_rotulo_de_padres_ya_no_dice_causa_de_hitos_previos(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)
        panel = _panel_for(ctrl, ps, payoff.id)

        assert "Causa de (hitos previos)" not in panel.links_label.text()
        assert "Consecuencias (hitos posteriores)" not in panel.links_label.text()
        assert panel.causes_caption.text() == "Recoge lo que plantó"
        assert panel.effects_caption.text() == "Consecuencias"

    def test_el_hito_no_se_ofrece_a_si_mismo_ni_repite_enlaces(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)
        panel = _panel_for(ctrl, ps, setup.id)
        efectos = [
            panel.link_effect_combo.itemData(i)
            for i in range(panel.link_effect_combo.count())
        ]
        causas = [
            panel.link_cause_combo.itemData(i)
            for i in range(panel.link_cause_combo.count())
        ]
        assert setup.id not in efectos and setup.id not in causas
        assert payoff.id not in efectos  # ya es consecuencia
        assert payoff.id not in causas  # y colgarlo como causa haría un ciclo


class TestPanelHilosSueltos:
    def test_lista_los_hilos_sueltos_y_abre_el_hito(self, qapp):
        ps, ctrl, setup, payoff = _setup()
        ctrl.link_causal(payoff.id, setup.id)
        abiertos: list[str] = []
        panel = LooseThreadsPanel(ctrl, on_open_milestone=abiertos.append)

        titulos = [
            panel.threads_list.item(i).text() for i in range(panel.threads_list.count())
        ]
        assert len(titulos) == 1  # el setup tiene payoff: no es hilo suelto
        assert "2x03" in titulos[0]

        panel._open_selected(panel.threads_list.item(0))
        assert abiertos == [payoff.id]

    def test_la_pildora_de_la_cronologia_abre_el_panel(self, qapp, tmp_path, monkeypatch):
        """Criterio 6: la superficie existe DE VERDAD en la Cronología.

        Los métodos del controlador (`causal_chain`, `hitos_without_consequences`)
        llevaban desde B41 sin un solo llamador en todo `hosts/`.
        """
        from PySide6.QtWidgets import QMessageBox

        import hosts.DesktopHostPySide.app_context as ac

        monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        from hosts.DesktopHostPySide.main_window import MainWindow
        from packages.domain.result import Ok

        ps = ProjectService(ProjectStore())
        assert isinstance(ps.create(name="Serie"), Ok)
        ctrl = CausalMilestoneController(ps)
        setup = ctrl.create_manual({"title": "1x03 — Caja negra", "year": 3}).value
        payoff = ctrl.create_manual({"title": "2x03 — La caja habla", "year": 20}).value
        ctrl.link_causal(payoff.id, setup.id)
        ruta = tmp_path / "serie.json"
        assert isinstance(ps.save(ruta), Ok)

        ventana = MainWindow()
        try:
            ventana._open_project_path(str(ruta))
            ws = ventana.creation_workspace
            ws.resize(1440, 900)
            ws.set_active_view("chrono")
            pildora = ws._float_threads
            assert pildora is not None and not pildora.isHidden()
            assert "1 hilo suelto" in pildora.text()  # solo el final, no los dos

            ws._open_loose_threads_panel()  # no revienta y monta el panel
            # fuera de la Cronología la píldora se calla
            ws.set_active_view("foco")
            assert pildora.isHidden()
        finally:
            ventana.close()
            ventana.deleteLater()

    def test_sin_hilos_sueltos_lo_dice(self, qapp):
        ps = ProjectService(ProjectStore())
        ps.create(name="Vacio")
        ctrl = CausalMilestoneController(ps)
        panel = LooseThreadsPanel(ctrl)

        assert panel.threads_list.isVisible() is False
        assert panel.empty_label.isVisibleTo(panel)
        assert "No hay hilos sueltos" in panel.empty_label.text()
