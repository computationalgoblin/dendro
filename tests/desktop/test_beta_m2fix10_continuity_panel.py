"""BETA-MULTIAGENT2-FIX-10: la Continuidad tiene puerta (pestaña «Salud del proyecto»).

El tester enumeró los botones visibles de la ventana entera y el único con pinta
de revisar algo era «! Reportar problema». Aquí se comprueba que la pestaña
existe, que agrupa en vez de volcar 19 tarjetas iguales, que descartar se le PIDE
al servicio (la UI no escribe persistencia) y que todo eso funciona con la IA
apagada.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.continuity_panel import ContinuityTab  # noqa: E402
from hosts.DesktopHostPySide.widgets.project_health_panel import (  # noqa: E402
    ProjectHealthPanel,
)
from packages.application.continuity_service import (  # noqa: E402
    FAMILIA_CALENDARIO,
    FAMILIA_DATACION,
    FAMILIA_HISTORIA,
    ContinuityGroup,
    ContinuityService,
)
from packages.application.temporal_coherence import TemporalIssue  # noqa: E402
from packages.domain.causal_milestone import (  # noqa: E402
    CausalMilestone,
    CausalMilestoneStatus,
    CausalMilestoneType,
)
from packages.domain.entity import EntityType, NarrativeEntity  # noqa: E402
from packages.domain.era import Era  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.domain.project_chronology import ProjectChronology  # noqa: E402
from packages.domain.result import Error, Ok  # noqa: E402
from packages.domain.temporal_span import TemporalSpan  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _issue(code, subject_id, mensaje):
    return TemporalIssue(
        code=code, message=mensaje, subject_kind="milestone", subject_id=subject_id
    )


class _FakeService:
    """Doble del ContinuityService: registra lo que le pide la pestaña."""

    def __init__(self, grupos=None, hilos=None):
        self._grupos = grupos if grupos is not None else []
        self._hilos = hilos or []
        self.descartes: list[str] = []

    def grouped(self):
        return Ok(list(self._grupos))

    def loose_threads(self):
        return Ok(list(self._hilos))

    @staticmethod
    def fingerprint(issue):
        return f"cont:{issue.subject_kind}:{issue.subject_id}:{issue.code}:"

    def dismiss(self, fingerprint):
        self.descartes.append(fingerprint)
        self._grupos = [
            ContinuityGroup(
                code=g.code,
                title=g.title,
                family=g.family,
                issues=[i for i in g.issues if self.fingerprint(i) != fingerprint],
            )
            for g in self._grupos
        ]
        self._grupos = [g for g in self._grupos if g.count]
        return Ok(True)


def _grupo_ruidoso():
    """19 avisos idénticos de calendario + su causa: el caso del mundo de Aitor."""
    return [
        ContinuityGroup(
            code="T10_BILOCATION",
            title="En dos sitios a la vez",
            family=FAMILIA_HISTORIA,
            issues=[_issue("T10_BILOCATION", "h1", "Nadia está en dos sitios el año 44.")],
        ),
        ContinuityGroup(
            code="T14_DATING_DESYNC",
            title="La ficha y el lapso guardado no coinciden",
            family=FAMILIA_DATACION,
            issues=[
                _issue("T14_DATING_DESYNC", f"e{n}", f"Ficha {n}: la ficha y el lapso difieren.")
                for n in range(19)
            ],
        ),
        ContinuityGroup(
            code="T02_OUTSIDE_ERAS",
            title="Fechas fuera de las eras del calendario",
            family=FAMILIA_CALENDARIO,
            issues=[
                _issue("T02_OUTSIDE_ERAS", f"e{n}", f"Ficha {n}: año fuera del calendario.")
                for n in range(19)
            ],
        ),
    ]


# ── La puerta ─────────────────────────────────────────────────────────────


def test_beta_m2fix10_es_una_pestana_del_panel_unico(qapp):
    """Decisión de producto: una sola puerta a «qué va mal», con pestañas."""
    panel = ProjectHealthPanel(None)
    panel.add_section("Continuidad", ContinuityTab(_FakeService()), index=0)
    titulos = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
    assert titulos[0] == "Continuidad"
    assert "Wiki" in titulos
    assert panel.show_section("Continuidad")


def test_beta_m2fix10_sin_avisos_lo_dice_sin_alarmar(qapp):
    tab = ContinuityTab(_FakeService([]))
    assert tab.refresh()
    assert tab.total() == 0
    assert "Sin avisos" in tab.summary.text()
    assert tab.list.count() == 0


def test_beta_m2fix10_sin_servicio_no_revienta(qapp):
    tab = ContinuityTab(None)
    assert tab.refresh() is False
    assert "No hay proyecto" in tab.summary.text()


def test_beta_m2fix10_error_del_servicio_se_enseña(qapp):
    class _Roto:
        def grouped(self):
            return Error("No hay proyecto activo")

    tab = ContinuityTab(_Roto())
    assert tab.refresh() is False
    assert "No hay proyecto activo" in tab.summary.text()


# ── Agrupación: 19 tarjetas iguales serían el fracaso ─────────────────────


def test_beta_m2fix10_agrupa_y_pliega_en_vez_de_volcar(qapp):
    tab = ContinuityTab(_FakeService(_grupo_ruidoso()))
    tab.refresh()
    assert tab.counts() == {
        "T10_BILOCATION": 1,
        "T14_DATING_DESYNC": 19,
        "T02_OUTSIDE_ERAS": 19,
    }
    assert tab.total() == 39
    filas = [tab.list.item(i).text() for i in range(tab.list.count())]
    # Cabeceras por familia y por grupo, con su recuento.
    assert any(f.strip() == "TU HISTORIA SE CONTRADICE" for f in filas)
    assert any(f.strip() == "19 · Fechas fuera de las eras del calendario" for f in filas)
    # Ni una sola familia vuelca sus 19 filas: se pliegan.
    assert any("… y 7 más" in f for f in filas)
    assert len(filas) < 39


def test_beta_m2fix10_explica_la_causa_del_ruido_de_calendario(qapp):
    """§5 del hallazgo: los 19 avisos de calendario vienen de una datación
    desincronizada, no de que el calendario esté mal."""
    tab = ContinuityTab(_FakeService(_grupo_ruidoso()))
    tab.refresh()
    filas = [tab.list.item(i).text() for i in range(tab.list.count())]
    assert any("NO coincide con lo que enseña la Ficha" in f for f in filas)
    assert any("Vuelve a guardar su datación" in f for f in filas)
    assert "39 avisos" in tab.summary.text()


def test_beta_m2fix10_hilos_sueltos_se_pintan_aparte(qapp):
    hito = CausalMilestone(id="h", title="2x08 — Habitable", year=16)
    tab = ContinuityTab(_FakeService([], hilos=[hito]))
    tab.refresh()
    assert tab.threads_list.isVisibleTo(tab)
    assert tab.threads_list.count() == 1
    assert tab.threads_list.item(0).text().startswith("2x08 — Habitable")
    assert "Plantado sin recoger" in tab.threads_label.text()


def test_beta_m2fix10_sin_hilos_sueltos_no_se_pinta_la_seccion(qapp):
    tab = ContinuityTab(_FakeService([]))
    tab.refresh()
    assert tab.threads_list.count() == 0
    assert not tab.threads_label.isVisibleTo(tab)


# ── Descartar: lo aplica el servicio, la UI no escribe ────────────────────


def test_beta_m2fix10_descartar_pide_al_servicio_y_pide_guardar(qapp):
    servicio = _FakeService(_grupo_ruidoso())
    guardados = []
    tab = ContinuityTab(servicio, on_dismissed=lambda: guardados.append(1))
    tab.refresh()
    fila = next(
        i
        for i in range(tab.list.count())
        if tab.list.item(i).data(Qt.ItemDataRole.UserRole)
    )
    tab.list.setCurrentRow(fila)
    assert tab.dismiss_btn.isEnabled()
    assert tab._dismiss_selected()
    assert servicio.descartes == ["cont:milestone:h1:T10_BILOCATION:"]
    assert guardados == [1]  # el guardado a disco se le pide al host
    assert "T10_BILOCATION" not in tab.counts()


def test_beta_m2fix10_sin_seleccion_no_se_puede_descartar(qapp):
    servicio = _FakeService(_grupo_ruidoso())
    tab = ContinuityTab(servicio)
    tab.refresh()
    tab.list.setCurrentRow(0)  # una cabecera: no lleva huella
    assert not tab.dismiss_btn.isEnabled()
    assert tab._dismiss_selected() is False
    assert servicio.descartes == []


# ── Integración con el servicio de verdad (cero IA, cero red) ─────────────


class _ProjectService:
    def __init__(self, project):
        self.active_project = project


def _mundo_con_bilocacion() -> Project:
    proj = Project(id="p", name="Órbita Muerta")
    proj.project_chronology = ProjectChronology(
        present_year=16, eras=[Era(name="Temporada 1", start_year=0, end_year=16)]
    )
    for eid, nombre, tipo, birth in (
        ("nadia", "Nadia Kerr", EntityType.PERSONAJE, 1),
        ("cubierta", "Cubierta 9", EntityType.LOCALIZACION, 0),
        ("estacion", "Estación Cernida", EntityType.LOCALIZACION, 0),
    ):
        entidad = NarrativeEntity(id=eid, name=nombre, entity_type=tipo)
        entidad.set_life_span(TemporalSpan.from_years(birth, None))
        proj.entities.append(entidad)
    for hid, titulo, lugar in (
        ("h1", "1x01 — Chatarra", "cubierta"),
        ("h2", "1x01b — Nadia en la Estación", "estacion"),
    ):
        proj.causal_milestones.append(
            CausalMilestone(
                id=hid,
                title=titulo,
                year=1,
                milestone_type=CausalMilestoneType.OTRO,
                status=CausalMilestoneStatus.CANON,
                affected_entity_ids=["nadia", lugar],
            )
        )
    return proj


def test_beta_m2fix10_con_el_servicio_real_y_la_ia_apagada(qapp):
    proj = _mundo_con_bilocacion()
    servicio = ContinuityService(_ProjectService(proj))
    guardados = []
    tab = ContinuityTab(servicio, on_dismissed=lambda: guardados.append(1))
    tab.refresh()
    assert tab.counts() == {"T10_BILOCATION": 1}

    fila = next(
        i for i in range(tab.list.count()) if tab.list.item(i).data(Qt.ItemDataRole.UserRole)
    )
    tab.list.setCurrentRow(fila)
    assert tab._dismiss_selected()
    assert tab.total() == 0
    assert guardados == [1]
    # El descarte vive en el hito, y el canon no se ha tocado.
    assert any(h.metadata.get("_continuity_dismissed") for h in proj.causal_milestones)
    assert proj.candidates == []
    assert len(proj.entities) == 3
