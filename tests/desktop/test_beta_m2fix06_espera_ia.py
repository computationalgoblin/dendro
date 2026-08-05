"""BETA-MULTIAGENT2-FIX-06 (G2-08): la espera de IA deja de ser silencio.

La diseñadora de producto muestreó el indicador de estado cada 250 ms durante cuatro
operaciones reales: **17 min 44 s de silencio absoluto de 29 min 36 de espera**. Regar
calló 269,2 s antes del primer mensaje; «Proponer estructura» sus 213,0 s enteros;
Play/walk sus 581,6 s enteros. Y la solución ya existía dentro del producto:
Sugerencias informa 8 veces, la primera a los 0,26 s.

Aquí se verifica que las tres superficies mudas usan el MISMO canal, que nadie paga
dos veces por regar y que el modal de «Configura la IA» no se repite.

``CreationWorkspace`` no se instancia sin un ``AppContext`` completo (patrón de la
casa): sus métodos se invocan sobre un doble por ``MethodType`` / ``__wrapped__``, y
el cableado que no se puede ejecutar se valida POR FUENTE, como en
``tests/desktop/test_ai_unconfigured_feedback.py``.
"""

from __future__ import annotations

import os
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace  # noqa: E402
from hosts.DesktopHostPySide.widgets.foco.watering_batch import (  # noqa: E402
    WateringBatchWorker,
)
from packages.domain.result import Ok  # noqa: E402

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _method_body(src: str, name: str) -> str:
    return src.split(f"def {name}(self")[1].split("\n    def ")[0]


# ── 1. El worker del lote propaga las fases (G2-08, criterio 2) ──────────────


class _ServicioConFases:
    """Servicio de riego que emite las fases del pipeline como hace el real."""

    def __init__(self) -> None:
        self.pasos: list[str] = []

    def water_batch_step(self, entity_id, *, batch_ids=None, progress_callback=None):
        self.pasos.append(entity_id)
        if callable(progress_callback):
            progress_callback(SimpleNamespace(message="Construyendo contexto...", progress=0.20))
            progress_callback(SimpleNamespace(message="Esperando al modelo...", progress=0.60))
        return Ok(None)


class _ServicioFirmaEstrecha:
    """Doble antiguo: NO acepta ``progress_callback`` (firma de antes de FIX-06)."""

    def __init__(self) -> None:
        self.pasos: list[str] = []

    def water_batch_step(self, entity_id, *, batch_ids=None):
        self.pasos.append(entity_id)
        return Ok(None)


def test_beta_m2fix06_worker_propaga_las_fases_por_signal():
    servicio = _ServicioConFases()
    worker = WateringBatchWorker(servicio, ["a", "b"])
    fases: list[tuple[str, str, int]] = []
    worker.phaseChanged.connect(lambda eid, msg, pct: fases.append((eid, msg, pct)))
    worker.run()  # síncrono en el test (sin hilo)
    assert servicio.pasos == ["a", "b"]
    assert fases[0] == ("a", "Construyendo contexto...", 20)
    assert ("a", "Esperando al modelo...", 60) in fases
    assert ("b", "Construyendo contexto...", 20) in fases


def test_beta_m2fix06_worker_no_rompe_un_servicio_de_firma_estrecha():
    """Trampa del ticket: un `TypeError` aquí se disfrazaba de «riego fallido»."""
    servicio = _ServicioFirmaEstrecha()
    worker = WateringBatchWorker(servicio, ["a"])
    assert worker.accepts_progress_callback() is False
    resultados: list[tuple[str, bool]] = []
    worker.entityDone.connect(lambda eid, ok, err: resultados.append((eid, ok)))
    worker.run()
    assert resultados == [("a", True)]  # regado, no «fallido en silencio»
    assert servicio.pasos == ["a"]


def test_beta_m2fix06_worker_detecta_la_firma_ancha():
    assert WateringBatchWorker(_ServicioConFases(), ["a"]).accepts_progress_callback() is True


# ── 2. Regar habla AL EMPEZAR, no al terminar la primera (criterio 1) ────────


def _doble_workspace():
    """Doble mínimo para invocar los slots del lote sin montar el workspace."""
    fake = SimpleNamespace()
    fake.textos: list[str] = []
    fake.logs: list[tuple[str, str]] = []
    fake.avisos: list[tuple[str, str]] = []
    fake._batch_state = {}
    fake._batch_total = 0
    fake._watering_status_prefix = ""
    fake._watering_progress_popover = None
    fake._job_status_label = SimpleNamespace(setText=fake.textos.append)
    fake.ctx = SimpleNamespace(
        log=lambda lvl, msg: fake.logs.append((lvl, msg)),
        notify=lambda msg, kind="info": fake.avisos.append((msg, kind)),
        request_save_silent=lambda: None,
    )
    fake.graph = SimpleNamespace(set_watering_active=lambda eid: None)
    fake.foco = SimpleNamespace(set_watering_active=lambda eid: None, notebook=None)
    fake._watering_panel = None
    fake._refresh_watering_progress_popover = lambda **k: None
    fake._get_active_project = lambda: SimpleNamespace(
        entity_by_id=lambda eid: SimpleNamespace(name="Aria" if eid == "e1" else "Beto")
    )
    fake._run_batch_cosmetics = types.MethodType(CreationWorkspace._run_batch_cosmetics, fake)
    fake._set_watering_triggers_busy = types.MethodType(
        CreationWorkspace._set_watering_triggers_busy, fake
    )
    fake._watering_prefix_for = types.MethodType(CreationWorkspace._watering_prefix_for, fake)
    return fake


def test_beta_m2fix06_entity_started_escribe_estado_al_empezar():
    fake = _doble_workspace()
    fake._batch_state = {"e1": "pending", "e2": "pending"}
    fake._batch_total = 2
    CreationWorkspace._on_watering_entity_started.__wrapped__(fake, "e1")
    assert fake.textos, "el slot de entityStarted seguía sin tocar el indicador"
    assert fake.textos[0] == "Regando «Aria» (1/2)…"  # (1/2) ANTES de regar, no después


def test_beta_m2fix06_segunda_entidad_cuenta_bien():
    fake = _doble_workspace()
    fake._batch_state = {"e1": "done", "e2": "pending"}
    fake._batch_total = 2
    CreationWorkspace._on_watering_entity_started.__wrapped__(fake, "e2")
    assert fake.textos[0] == "Regando «Beto» (2/2)…"


def test_beta_m2fix06_las_fases_se_pegan_al_encabezado():
    fake = _doble_workspace()
    fake._batch_state = {"e1": "watering"}
    fake._batch_total = 1
    fake._watering_status_prefix = "Regando «Aria» (1/1)"
    CreationWorkspace._on_watering_phase.__wrapped__(fake, "e1", "Construyendo contexto...", 20)
    assert fake.textos == ["Regando «Aria» (1/1) · Construyendo contexto... (20 %)"]


def test_beta_m2fix06_una_fase_rezagada_no_pisa_el_paso_siguiente():
    fake = _doble_workspace()
    fake._batch_state = {"e1": "done", "e2": "watering"}
    fake._watering_status_prefix = "Regando «Beto» (2/2)"
    CreationWorkspace._on_watering_phase.__wrapped__(fake, "e1", "Esperando al modelo...", 60)
    assert fake.textos == []


def test_beta_m2fix06_el_lote_habla_antes_de_arrancar_el_hilo():
    """El primer texto se escribe ANTES de `worker.start()` (criterio 1)."""
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = _method_body(src, "_run_watering_batch")
    assert "self._job_status_label.setText" in body
    assert body.index("self._job_status_label.setText") < body.index("worker.start()")
    assert "worker.phaseChanged.connect(self._on_watering_phase)" in body


# ── 3. Nadie paga dos veces por regar (criterio 3) ───────────────────────────


class _WorkerVivo:
    def isRunning(self):  # noqa: N802 (API Qt)
        return True


def _doble_con_lote_en_vuelo():
    fake = SimpleNamespace()
    fake.avisos: list[tuple[str, str]] = []
    fake._watering_worker = _WorkerVivo()
    fake.watering_service = SimpleNamespace(
        entities_in_scope=lambda _scope: pytest.fail("no debe llegar a estimar un segundo lote")
    )
    fake.ai_job_service = SimpleNamespace(provider_unconfigured=lambda: False)
    fake.ctx = SimpleNamespace(
        notify=lambda msg, kind="info": fake.avisos.append((msg, kind)),
        log=lambda lvl, msg: None,
    )
    fake._watering_batch_running = types.MethodType(
        CreationWorkspace._watering_batch_running, fake
    )
    fake._reject_second_batch = types.MethodType(CreationWorkspace._reject_second_batch, fake)
    return fake


def test_beta_m2fix06_segundo_on_foco_water_se_rechaza_con_aviso():
    fake = _doble_con_lote_en_vuelo()
    CreationWorkspace._on_foco_water(fake, ["e1"])
    assert fake.avisos and "riego en curso" in fake.avisos[0][0]


def test_beta_m2fix06_segundo_run_watering_batch_no_arranca_otro_worker():
    fake = _doble_con_lote_en_vuelo()
    anterior = fake._watering_worker
    CreationWorkspace._run_watering_batch(fake, ["e1"])
    assert fake._watering_worker is anterior  # no se sobrescribió con un segundo worker
    assert fake.avisos


def test_beta_m2fix06_sin_lote_en_vuelo_no_hay_rechazo():
    fake = _doble_con_lote_en_vuelo()
    fake._watering_worker = None
    assert fake._watering_batch_running() is False
    assert fake._reject_second_batch() is False


# ── 4. Los tres disparadores se apagan mientras riega (criterio 3) ───────────


def test_beta_m2fix06_cuaderno_apaga_su_boton_regar_ahora():
    from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import CultivationNotebook

    notebook = CultivationNotebook()
    notebook._set_step("water", "", "Falta regar.", "Regar ahora")
    assert notebook.step_button.isEnabled()
    notebook.set_batch_running(True)
    assert not notebook.step_button.isEnabled()
    # Un refresco del paso EN MEDIO del lote no lo resucita (el estado es un campo).
    notebook._set_step("water", "", "Falta regar.", "Regar de nuevo")
    assert not notebook.step_button.isEnabled()
    notebook.set_batch_running(False)
    assert notebook.step_button.isEnabled()
    notebook.deleteLater()


def test_beta_m2fix06_next_step_chip_tiene_estado_ocupado():
    from hosts.DesktopHostPySide.widgets.foco.next_step_chip import NextStepChip
    from packages.application.watering_guidance import NextStep

    chip = NextStepChip()
    chip.set_step(NextStep(kind="water"))
    assert chip.isEnabled()
    chip.set_busy(True)
    assert not chip.isEnabled()
    disparos: list[bool] = []
    chip.waterClicked.connect(lambda: disparos.append(True))
    chip._on_clicked()  # ni siquiera por código dispara mientras riega
    assert disparos == []
    chip.set_step(NextStep(kind="water"))  # un refresco no lo resucita
    assert not chip.isEnabled()
    chip.set_busy(False)
    assert chip.isEnabled()
    chip.deleteLater()


def test_beta_m2fix06_watering_panel_recuerda_el_lote_en_vuelo():
    """`set_batch_running` era código muerto y `refresh()` lo habría deshecho igual."""
    from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel

    reporte = SimpleNamespace(
        status="falta_regar",
        latest=None,
        stale=False,
        last_error="",
    )
    servicio = SimpleNamespace(
        status_of=lambda eid: SimpleNamespace(value=reporte),
        history_for=lambda eid: SimpleNamespace(value=[]),
    )
    panel = WateringPanel(servicio)
    panel._entity_id = "e1"
    panel.refresh()
    assert panel.water_button.isEnabled()
    panel.set_batch_running(True)
    assert not panel.water_button.isEnabled()
    panel.refresh()  # el lote refresca a cada paso: NO puede revivir el botón
    assert not panel.water_button.isEnabled()
    panel.set_batch_running(False)
    panel.refresh()
    assert panel.water_button.isEnabled()
    panel.deleteLater()


def test_beta_m2fix06_el_workspace_apaga_y_reenciende_los_disparadores():
    from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import CultivationNotebook
    from hosts.DesktopHostPySide.widgets.foco.next_step_chip import NextStepChip

    notebook = CultivationNotebook()
    notebook._set_step("water", "", "Falta regar.", "Regar ahora")
    chip = NextStepChip()
    panel = SimpleNamespace(estados=[], set_batch_running=lambda b: panel.estados.append(b))

    fake = SimpleNamespace()
    fake.foco = SimpleNamespace(notebook=notebook, next_step_chip=chip)
    fake._watering_panel = panel
    aplicar = types.MethodType(CreationWorkspace._set_watering_triggers_busy, fake)

    aplicar(True)
    assert not notebook.step_button.isEnabled()
    assert chip.busy() is True
    assert panel.estados == [True]

    aplicar(False)
    assert notebook.step_button.isEnabled()
    assert chip.busy() is False
    assert panel.estados == [True, False]
    notebook.deleteLater()
    chip.deleteLater()


def test_beta_m2fix06_el_lote_apaga_al_arrancar_y_reenciende_al_terminar():
    src = _WORKSPACES.read_text(encoding="utf-8")
    arranque = _method_body(src, "_run_watering_batch")
    fin = _method_body(src, "_on_watering_finished")
    assert "self._set_watering_triggers_busy(True)" in arranque
    assert "self._set_watering_triggers_busy(False)" in fin


# ── 5. El modal «Configura la IA» va UNA vez por sesión (criterio 4) ─────────


def test_beta_m2fix06_cinco_intentos_un_solo_modal():
    fake = SimpleNamespace()
    fake.avisos: list[tuple[str, str]] = []
    fake.dialogos: list[int] = []
    fake.ctx = SimpleNamespace(notify=lambda msg, kind="info": fake.avisos.append((msg, kind)))
    fake._show_ai_config_help = lambda: fake.dialogos.append(1)
    avisar = types.MethodType(CreationWorkspace._warn_ai_unconfigured, fake)
    for _ in range(5):
        avisar("regar")
    assert len(fake.dialogos) == 1  # medido por la tester: 5 clics = 5 modales en 0,33 s
    assert len(fake.avisos) == 5  # el toast SÍ sale siempre (no bloquea)
    assert all(kind == "error" for _msg, kind in fake.avisos)


def test_beta_m2fix06_el_toast_sigue_en_el_cuerpo_del_aviso():
    """Guarda de la ronda 1: la guarda envuelve SOLO al diálogo, nunca al toast."""
    body = _method_body(_WORKSPACES.read_text(encoding="utf-8"), "_warn_ai_unconfigured")
    assert "self.ctx.notify(" in body
    assert 'kind="error"' in body
    assert "self._show_ai_config_help()" in body
    guarda = 'getattr(self, "_ai_config_hint_shown", False)'
    assert guarda in body
    assert body.index("self.ctx.notify(") < body.index(guarda)  # el toast va SIEMPRE primero


# ── 6. Play/walk deja de ser mudo (criterio 5) ───────────────────────────────


def test_beta_m2fix06_el_paso_de_play_anuncia_al_arrancar():
    fake = SimpleNamespace(textos=[])
    fake._job_status_label = SimpleNamespace(setText=fake.textos.append)
    types.MethodType(CreationWorkspace._announce_walk_step, fake)()
    assert fake.textos and "Analizando el hito" in fake.textos[0]


@pytest.mark.parametrize(
    ("cambios", "esperado"), [(0, "no propone cambios"), (3, "3 cambio(s)")]
)
def test_beta_m2fix06_el_paso_de_play_anuncia_su_desenlace(cambios, esperado):
    textos: list[str] = []
    avisos: list[tuple[str, str]] = []
    fake = SimpleNamespace()
    fake._job_status_label = SimpleNamespace(setText=textos.append)
    fake._schedule_status_clear = lambda *a, **k: None
    fake.ctx = SimpleNamespace(notify=lambda msg, kind="info": avisos.append((msg, kind)))
    types.MethodType(CreationWorkspace._announce_walk_outcome, fake)(cambios)
    assert esperado in textos[0]
    assert avisos and esperado in avisos[0][0]  # toast, no ctx.log oculto


def test_beta_m2fix06_el_walk_escribe_en_el_canal_compartido():
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "self._announce_walk_step()" in _method_body(src, "_run_walk_step")
    assert "self._announce_walk_outcome(" in _method_body(src, "_on_walk_step_done")
    fallo = _method_body(src, "_on_walk_step_failed")
    assert "self._job_status_label.setText" in fallo
    assert "self.ctx.notify(" in fallo
    vigilante = _method_body(src, "_on_walk_watchdog_timeout")
    assert "self._job_status_label.setText" in vigilante


# ── 7. «Proponer estructura» deja de ser mudo (criterio 5) ───────────────────


class _ServicioEstructura:
    def analyze(self):
        return Ok([])

    def structure_proposals(self):
        return []


def _panel_con_canal():
    from hosts.DesktopHostPySide.widgets.structure_review_panel import StructureReviewPanel

    avisos: list[tuple[str, str]] = []
    estados: list[str] = []
    panel = StructureReviewPanel(
        _ServicioEstructura(),
        on_accept=lambda f: None,
        notify=lambda msg, kind="info": avisos.append((msg, kind)),
        status=estados.append,
    )
    return panel, avisos, estados


def test_beta_m2fix06_estructura_anuncia_cero_propuestas():
    panel, avisos, estados = _panel_con_canal()
    panel._on_propose_done.__wrapped__(panel, Ok([]))
    assert avisos and "no ve cambios de estructura" in avisos[0][0]
    assert estados and "no ve cambios de estructura" in estados[0]
    panel.deleteLater()


def test_beta_m2fix06_estructura_anuncia_el_timeout_como_error():
    panel, avisos, estados = _panel_con_canal()
    panel._on_propose_done.__wrapped__(panel, TimeoutError("The read operation timed out"))
    assert avisos and avisos[0][1] == "error"
    assert "timed out" in avisos[0][0]
    assert estados
    panel.deleteLater()


def test_beta_m2fix06_estructura_escribe_estado_al_arrancar():
    panel, _avisos, estados = _panel_con_canal()
    panel._proposing = True  # evita lanzar el hilo real: se prueba la guarda + estado
    panel._propose_structure()
    assert estados == []  # con una propuesta en vuelo no se dispara otra (SHIP-07)
    panel._proposing = False
    panel._service = SimpleNamespace(
        analyze=lambda: Ok([]),
        structure_proposals=lambda: [],
        propose_ring_structure=lambda: Ok([]),
    )
    panel._propose_structure()
    assert estados and "Proponiendo estructura" in estados[0]
    worker = panel._propose_worker
    if worker is not None:
        worker.wait(5000)
    panel.deleteLater()


def test_beta_m2fix06_el_workspace_cablea_el_canal_del_panel_de_estructura():
    body = _method_body(_WORKSPACES.read_text(encoding="utf-8"), "_open_structure_panel")
    assert "notify=self.ctx.notify" in body
    assert "status=self._job_status_label.setText" in body
