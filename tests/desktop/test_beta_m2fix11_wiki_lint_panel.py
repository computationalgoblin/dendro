"""BETA-MULTIAGENT2-FIX-11 (fase A): el lint de la wiki tiene pantalla.

`WikiLintService` existía, funcionaba y tenía CERO importadores en `hosts/`: en los
mundos del beta detectaba 17 y 27 enlaces rotos que nadie veía («el lint sí los
detecta; lo que falta es que alguien mire el lint», Rubén). Ahora vive en la
pestaña Wiki del panel «Salud del proyecto»: bajo demanda, determinista, sin
contador permanente en la esquina (G2-07) y funcionando con la IA apagada.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import dataclass  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.memory_viewer_panel import element_label  # noqa: E402
from hosts.DesktopHostPySide.widgets.project_health_panel import (  # noqa: E402
    ProjectHealthPanel,
)
from packages.application.wiki_lint_service import WikiLintService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.narrative_memory import (  # noqa: E402
    MemoryCitation,
    MemoryFreshness,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@dataclass
class _FakeProjectService:
    active_project: Project = None


class _FakeAIJobs:
    """Doble del AIJobService: `configured` decide si hay proveedor."""

    def __init__(self, configured: bool):
        self._configured = configured
        self.calls = 0

    def provider_unconfigured(self) -> bool:
        return not self._configured

    def raw_json_completion(self, system, user):  # pragma: no cover - no se usa aquí
        self.calls += 1
        return '{"contradicciones": []}', None


def _project() -> Project:
    p = Project(id="p", name="Castilla")
    p.entities.append(NarrativeEntity(id="e1", name="Pedro I"))
    page = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id="e1",
        resumen_editorial="El rey.",
        cuerpo="Reinó entre 1350 y 1369.",
    )
    # Un wikilink a un id que no existe: exactamente el caso de los 17/27 rotos.
    page.wikilinks.append(
        MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="maria-de-padilla")
    )
    p.narrative_memories.append(page)
    return p


def _panel(configured: bool = False, on_open=None):
    ps = _FakeProjectService(active_project=_project())
    lint = WikiLintService(ps, ai_job_service=_FakeAIJobs(configured))
    panel = ProjectHealthPanel(
        lint,
        on_open_page=on_open,
        element_label=lambda kind, tid: element_label(ps.active_project, kind, tid),
    )
    return panel, ps


def test_beta_m2fix11_panel_tiene_pestana_wiki(qapp):
    panel, _ = _panel()
    titulos = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
    assert "Wiki" in titulos
    # La API de pestañas queda lista para Continuidad (FIX-10) y Estructura.
    panel.add_section("Continuidad", panel.wiki_tab.__class__(None), index=0)
    assert panel.tabs.tabText(0) == "Continuidad"
    assert panel.show_section("Wiki")


def test_beta_m2fix11_lint_pinta_enlace_roto_sin_ia(qapp):
    panel, _ = _panel(configured=False)
    tab = panel.wiki_tab
    # Bajo demanda: nada calculado hasta que el usuario pulsa.
    assert tab.counts() == {}
    assert tab.run_lint()
    assert tab.counts()["broken_links"] == 1
    assert "1 enlace roto" in tab.summary.text()
    filas = [tab.list.item(i).text() for i in range(tab.list.count())]
    assert any("Pedro I" in f and "maria-de-padilla" in f for f in filas)


def test_beta_m2fix11_boton_ia_deshabilitado_sin_proveedor(qapp):
    panel, _ = _panel(configured=False)
    tab = panel.wiki_tab
    assert not tab.ai_available()
    assert not tab.ai_btn.isEnabled()
    assert "proveedor de ia" in tab.ai_btn.toolTip().lower()
    # Y el lint determinista corre igual.
    assert tab.run_lint()


def test_beta_m2fix11_boton_ia_habilitado_con_proveedor(qapp):
    panel, _ = _panel(configured=True)
    tab = panel.wiki_tab
    assert tab.ai_available()
    assert tab.ai_btn.isEnabled()


def test_beta_m2fix11_fila_navega_a_la_pagina(qapp):
    destinos = []
    panel, _ = _panel(on_open=destinos.append)
    tab = panel.wiki_tab
    tab.run_lint()
    fila = next(
        tab.list.item(i)
        for i in range(tab.list.count())
        if tab.list.item(i).data(Qt.ItemDataRole.UserRole)
    )
    tab._open_selected(fila)
    assert destinos == [("entity", "e1", "")]


def test_beta_m2fix11_wiki_limpia_lo_dice(qapp):
    ps = _FakeProjectService(active_project=Project(id="p", name="P"))
    panel = ProjectHealthPanel(WikiLintService(ps, ai_job_service=_FakeAIJobs(False)))
    assert panel.wiki_tab.run_lint()
    assert "limpia" in panel.wiki_tab.summary.text()
    assert panel.wiki_tab.list.count() == 0


def test_beta_m2fix11_obsoletas_y_huerfanas_se_cuentan(qapp):
    ps = _FakeProjectService(active_project=_project())
    proj = ps.active_project
    proj.narrative_memories[0].freshness = MemoryFreshness.FALTA_REGAR
    proj.narrative_memories.append(
        NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="borrada")
    )
    panel = ProjectHealthPanel(
        WikiLintService(ps, ai_job_service=_FakeAIJobs(False)),
        element_label=lambda kind, tid: element_label(proj, kind, tid),
    )
    tab = panel.wiki_tab
    assert tab.run_lint()
    conteos = tab.counts()
    assert conteos["stale"] == 1
    assert conteos["orphans"] == 1
    assert conteos["broken_links"] == 1
    filas = [tab.list.item(i).text() for i in range(tab.list.count())]
    assert any("elemento eliminado" in f for f in filas)  # ni aquí se enseña el uuid


def test_beta_m2fix11_sin_proyecto_no_revienta(qapp):
    ps = _FakeProjectService(active_project=None)
    panel = ProjectHealthPanel(WikiLintService(ps))
    assert not panel.wiki_tab.run_lint()
    assert panel.wiki_tab.summary.text()


def test_beta_m2fix11_la_pantalla_tiene_puerta_viva(qapp):
    """El lint no puede quedarse otra vez sin botón: puerta en el Home + cableado."""
    from pathlib import Path

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.views.home_view import HomeView

    home = HomeView(AppContext())
    pulsado = []
    home.register_callback("health_menu", lambda: pulsado.append(True))
    assert home._btn_health.text()  # con ETIQUETA, no un icono mudo (G2-19)
    home._btn_health.click()
    assert pulsado == [True]

    fuente = Path("hosts/DesktopHostPySide/main_window.py").read_text(encoding="utf-8")
    assert 'register_callback("health_menu", self._open_health_panel)' in fuente
    assert "WikiLintService" in fuente  # el servicio se construye en el host


def test_beta_m2fix11_lint_no_muta_el_proyecto(qapp):
    """La pantalla es de MIRAR: el lint no escribe nada en el proyecto."""
    ps = _FakeProjectService(active_project=_project())
    antes = ps.active_project.to_dict()
    panel = ProjectHealthPanel(WikiLintService(ps, ai_job_service=_FakeAIJobs(False)))
    assert panel.wiki_tab.run_lint()
    assert isinstance(WikiLintService(ps).lint(), Ok)
    assert ps.active_project.to_dict() == antes
