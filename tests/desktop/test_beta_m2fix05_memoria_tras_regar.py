"""BETA2-FIX-05 (G2-06): tras regar, el Cuaderno repinta la MEMORIA.

Escena descrita por dos testers distintos de la ronda 2 (GUI-13 y CAR-03): el riego
termina, el chip de arriba dice «Regada», las métricas se actualizan… y tres centímetros
más abajo, en la MISMA pantalla, la sección MEMORIA sigue diciendo «Sin memoria —
Riégalo para generarla» con la página ya escrita en el JSON. Coste real: invita a pagar
otro riego por algo que ya está hecho.

El eslabón que faltaba era `FocoView.refresh_cultivation()`, el punto único por el que
pasan el fin de lote, el fin de entidad, secar y cultivar: llamaba a `notebook.refresh()`
(métricas/estado) y nunca a `notebook.refresh_memory()`.

Al final del fichero, la parte de UI de G2-07: las píldoras del jardín (💧 y ⚙) no se
pintan con la IA apagada ni dentro de Play — la guarda de proveedor existía solo en el
clic, así que la app facturaba de forma permanente un trabajo imposible de hacer.
"""

from __future__ import annotations

import os
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
from packages.domain.narrative_memory import (  # noqa: E402
    MemoryFreshness,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _FakeWateringService:
    """Estado de riego mínimo: el Cuaderno solo pide `status_of` e `history_for`."""

    def __init__(self, status: str = "regada"):
        self._report = SimpleNamespace(status=status, latest=None, stale=False, last_error="")

    def status_of(self, entity_id):
        return SimpleNamespace(value=self._report)

    def history_for(self, entity_id):
        return SimpleNamespace(value=[])


class _MemoryServiceQueVaEscribiendo:
    """`get_memory` EN VIVO: devuelve None hasta que el riego escribe la página.

    Reproduce el proveedor real que instala `FocoView` (un lambda sobre
    `mem_svc.get_memory`), que es justamente por lo que el arreglo es una llamada y no
    un rediseño: el bloque nuevo ya está disponible cuando termina el riego.
    """

    def __init__(self) -> None:
        self.entity_id = ""  # lo fija _foco cuando la entidad ya existe
        self.pagina: NarrativeMemory | None = None

    def get_memory(self, kind, target_id, context: str = ""):
        return Ok(self.pagina if target_id == self.entity_id else None)

    def regar(self) -> None:
        self.pagina = NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id=self.entity_id,
            resumen_editorial="Ilva, aprendiza de rojos: heredera del taller.",
            freshness=MemoryFreshness.REGADA,
        )


def _foco(memory_service, *, status: str = "regada"):
    """FocoView con la pestaña Cultivo REAL montada (patrón de test_foco_form_panels).

    El Cuaderno solo se construye si el Foco es `_form_capable()` (ctx +
    entity_controller): sin eso no hay pestaña Cultivo y no habría nada que repintar.
    """
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    project_service = ProjectService()
    project_service.create("Jardín FIX2-05")
    entity = NarrativeEntity(name="Ilva Cinabrio")
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )
    view = FocoView(
        project_provider=lambda: project_service.active_project,
        ctx=ctx,
        entity_controller=EntityController(project_service),
        watering_service=_FakeWateringService(status),
    )
    # El host lo asigna igual: FocoView solo instala el proveedor si hay servicio.
    if memory_service is not None:
        memory_service.entity_id = entity.id
    view.memory_service = memory_service
    view.center_entity(entity.id)
    return view, entity.id


def test_beta_m2fix05_refresh_cultivation_repinta_la_memoria(qapp):
    """Criterio 5: sin cambiar de entidad ni reabrir el proyecto, la página aparece."""
    mem = _MemoryServiceQueVaEscribiendo()
    view, _entity_id = _foco(mem)

    seccion = view.notebook.memory_section
    view.notebook.refresh_memory()
    assert "Sin memoria" in seccion.freshness_chip.text()

    # …el riego escribe la página (auto-aplica, BETA2-MEM-07) y termina.
    mem.regar()
    view.refresh_cultivation()  # el camino público del final del riego

    assert "Sin memoria" not in seccion.freshness_chip.text()
    assert "Memoria vigente" in seccion.freshness_chip.text()
    assert "aprendiza de rojos" in seccion.summary.text()


def test_beta_m2fix05_focoview_refresca_memoria_al_terminar_el_riego(qapp):
    """El eslabón exacto: `refresh_cultivation()` invoca `refresh_memory()`."""
    mem = _MemoryServiceQueVaEscribiendo()
    view, _entity_id = _foco(mem)

    llamadas: list[str] = []
    original = view.notebook.refresh_memory
    view.notebook.refresh_memory = lambda: (llamadas.append("memoria"), original())[1]

    view.refresh_cultivation()
    assert llamadas == ["memoria"]


def test_beta_m2fix05_sin_memory_service_no_rompe(qapp):
    """Sin `memory_service` el proveedor no se instala: refrescar no puede lanzar."""
    view, _entity_id = _foco(None)
    assert view.notebook is not None
    view.refresh_cultivation()  # no debe lanzar
    assert "Sin memoria" in view.notebook.memory_section.freshness_chip.text()


def test_beta_m2fix05_secar_y_cultivar_tambien_repintan(qapp):
    """`refresh_cultivation` es el punto único: secar/cultivar heredan el arreglo."""
    mem = _MemoryServiceQueVaEscribiendo()
    view, _entity_id = _foco(mem, status="secada")
    mem.regar()

    view.refresh_cultivation()
    assert "Memoria vigente" in view.notebook.memory_section.freshness_chip.text()


# ── G2-07: las píldoras del jardín no facturan lo imposible ─────────────────


def _suprimidas(*, vista: str, ia_apagada: bool) -> bool:
    """Evalúa la guarda REAL de `CreationWorkspace` sobre un doble mínimo.

    Se invoca el método sin construir el workspace entero (500+ widgets, y este test
    no habla de layout): lo que se comprueba es la REGLA, que es lo que falló.
    """
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    doble = SimpleNamespace(
        _active_view=vista,
        ai_job_service=SimpleNamespace(provider_unconfigured=lambda: ia_apagada),
    )
    return CreationWorkspace._garden_pills_suppressed(doble)


def test_beta_m2fix05_pildoras_calladas_sin_proveedor_de_ia(qapp):
    """Criterio 6: con la IA apagada no se factura un servicio inexistente (SIA-01).

    La guarda existía solo en el CLIC (`_warn_ai_unconfigured`), no en el refresco del
    badge: la deuda se contabilizaba de forma permanente y en todas las vistas.
    """
    assert _suprimidas(vista="concentric", ia_apagada=True) is True
    assert _suprimidas(vista="foco", ia_apagada=True) is True


def test_beta_m2fix05_pildoras_no_se_pintan_dentro_de_play(qapp):
    """Criterio 7: Marta las fotografió sobre la vista inmersiva (SIA-12)."""
    assert _suprimidas(vista="play", ia_apagada=False) is True


def test_beta_m2fix05_pildoras_vivas_en_el_caso_normal(qapp):
    """Con proveedor y fuera de Play siguen visibles (STRUCT-08 no se rompe)."""
    assert _suprimidas(vista="concentric", ia_apagada=False) is False
    assert _suprimidas(vista="foco", ia_apagada=False) is False


def test_beta_m2fix05_sin_servicio_de_ia_tambien_calla(qapp):
    """Sin `ai_job_service` (app sin IA) tampoco se ofrece trabajo imposible."""
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    doble = SimpleNamespace(_active_view="foco", ai_job_service=None)
    assert CreationWorkspace._garden_pills_suppressed(doble) is True
