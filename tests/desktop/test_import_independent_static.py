"""UX33 — Importación independiente: chequeos estáticos + slot de finalización.

Confirma el cableado del runner persistente (la vista delega en ctx.import_jobs, ya
no posee QThreads), la entrada en el canvas, la semilla de import y el autoguardado
silencioso, sin levantar toda la UI salvo para el slot de fin.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "hosts" / "DesktopHostPySide"
RUNNER = HOST / "controllers" / "import_job_runner.py"
VIEW = HOST / "views" / "import_export_view.py"
WORKSPACES = HOST / "views" / "workspaces.py"
MAIN = HOST / "main_window.py"
APPCTX = HOST / "app_context.py"


def test_runner_exists_and_owns_workers():
    text = RUNNER.read_text(encoding="utf-8")
    assert "class ImportJobRunner" in text
    assert "class _ImportExtractionWorker" in text
    assert "class _ScaffoldingWorker" in text
    assert "def start_extraction" in text and "def start_scaffolding" in text
    assert "def shutdown" in text


def test_view_no_longer_owns_qthreads():
    text = VIEW.read_text(encoding="utf-8")
    # Los workers se movieron al runner; la vista ya no los define ni importa QThread.
    assert "class _ImportExtractionWorker" not in text
    assert "class _ScaffoldingWorker" not in text
    assert "QThread" not in text
    # Dispara vía el runner persistente.
    assert "self.jobs.start_extraction(" in text
    assert "self.jobs.start_scaffolding(" in text
    assert 'getattr(ctx, "import_jobs", None)' in text
    # UX33: al (re)abrir la vista refresca para reflejar progreso / propuesta pendiente.
    assert "def showEvent" in text
    assert "_reflect_running_jobs" in text


def test_canvas_has_import_entry_and_seed():
    text = WORKSPACES.read_text(encoding="utf-8")
    assert '("project", "Importar documento", self._open_import_utility)' in text
    assert "def _open_import_utility" in text
    assert "def add_import_seed" in text
    # La semilla de import reabre la importación (no el panel de candidatos).
    assert 'startswith("import:")' in text


def test_mainwindow_wires_runner_and_silent_save():
    text = MAIN.read_text(encoding="utf-8")
    assert "ImportJobRunner(self.controller" in text
    assert "self.ctx.import_jobs = self.import_job_runner" in text
    assert "def _save_active_project_silent" in text
    assert "def _on_import_extraction_done" in text
    assert "self.creation_workspace._on_open_import = self._import_document" in text
    assert "runner.shutdown()" in text


def test_appcontext_has_import_fields():
    text = APPCTX.read_text(encoding="utf-8")
    assert "import_jobs" in text
    assert "request_save_silent" in text


# ── Comportamiento del slot de finalización (UX33) ───────────────────────

@pytest.fixture(scope="module")
def main_window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.main_window import MainWindow

    QApplication.instance() or QApplication([])
    win = MainWindow()
    yield win


def test_extraction_done_autosaves_notifies_and_seeds(main_window, monkeypatch):
    win = main_window
    saves: list[bool] = []
    notes: list[tuple] = []
    seeds: list[tuple] = []
    monkeypatch.setattr(win, "_save_active_project_silent", lambda: saves.append(True) or True)
    win.ctx.notify_sink = lambda msg, kind="info": notes.append((msg, kind))
    monkeypatch.setattr(
        win.creation_workspace, "add_import_seed",
        lambda bid, count: seeds.append((bid, count)),
    )

    win._on_import_extraction_done("b1", 4, "")

    assert saves == [True]                      # autoguardado una vez
    assert any(k == "success" for _m, k in notes)  # toast de éxito
    assert seeds == [("b1", 4)]                 # semilla añadida


def _set_basket_with_extraction_meta(win, basket_id, meta):
    from packages.domain.import_models import ImportBasket
    from packages.domain.project import Project
    proj = Project(name="I24meta")
    proj.import_baskets = [ImportBasket(
        id=basket_id, source_id="s", segments=[], import_candidates=[],
        review_state="pendiente", import_mode="canon",
        metadata={"ai_extraction": meta},
    )]
    win.controller.ps.active_project = proj


def test_extraction_partial_skipped_autosaves_and_seeds(main_window, monkeypatch):
    """I24: extracción parcial (secciones omitidas por el filtro) → autoguarda, avisa
    'parcial' y siembra (lo extraído es revisable)."""
    win = main_window
    saves: list[bool] = []
    notes: list[tuple] = []
    seeds: list[tuple] = []
    _set_basket_with_extraction_meta(win, "bp", {
        "aborted": False, "skipped_sections": 2, "pending_sections": 0,
    })
    monkeypatch.setattr(win, "_save_active_project_silent", lambda: saves.append(True) or True)
    win.ctx.notify_sink = lambda msg, kind="info": notes.append((msg, kind))
    monkeypatch.setattr(win.creation_workspace, "add_import_seed",
                        lambda bid, count: seeds.append((bid, count)))

    win._on_import_extraction_done("bp", 5, "")

    assert saves == [True]
    assert any(k == "info" and "parcial" in m.lower() for m, k in notes)
    assert seeds == [("bp", 5)]


def test_extraction_aborted_saves_progress_and_offers_resume(main_window, monkeypatch):
    """I24: corte sistémico → autoguarda el progreso (reanudable) y avisa
    'interrumpida' SIN sembrar (no es un resultado terminal)."""
    win = main_window
    saves: list[bool] = []
    notes: list[tuple] = []
    seeds: list[tuple] = []
    _set_basket_with_extraction_meta(win, "ba", {
        "aborted": True, "abort_reason": "HTTP 401: Unauthorized",
        "skipped_sections": 0, "pending_sections": 3,
    })
    monkeypatch.setattr(win, "_save_active_project_silent", lambda: saves.append(True) or True)
    win.ctx.notify_sink = lambda msg, kind="info": notes.append((msg, kind))
    monkeypatch.setattr(win.creation_workspace, "add_import_seed",
                        lambda bid, count: seeds.append((bid, count)))

    win._on_import_extraction_done("ba", 2, "")

    assert saves == [True]                                  # progreso guardado
    assert any(k == "error" and "interrump" in m.lower() for m, k in notes)
    assert seeds == []                                      # no siembra en corte


def test_view_has_resume_extraction_card():
    text = VIEW.read_text(encoding="utf-8")
    assert "_make_resume_card" in text and "def _needs_resume" in text
    assert "Reanudar análisis IA" in text


def test_reopening_import_shows_pending_scaffolding_card(main_window):
    """Regresión UX33: al reabrir la importación, la propuesta de andamiaje
    pendiente DEBE mostrarse para poder aceptarla/rechazarla (no depender de
    showEvent, que no llega fiable al montarse en el cajón animado)."""
    from packages.domain.import_models import ImportBasket
    from packages.domain.project import Project

    win = main_window
    proj = Project(name="Repro")
    basket = ImportBasket(
        id="b-reopen", source_id="s1", segments=[], import_candidates=[],
        review_state="pendiente", import_mode="canon",
        metadata={"project_config_suggestion": {
            "chronology": {"mode": "vague_periods", "eras": []},
            "world_layers": {"activate_default_layer_ids": [], "custom_layers": []},
            "milestones": [], "applied": False,
        }},
    )
    proj.import_baskets = [basket]
    win.controller.ps.active_project = proj

    win._import_document()  # camino real de (re)apertura
    view = win.import_export_view
    grid = view.cards_grid
    titles = [
        getattr(getattr(grid.itemAt(i).widget(), "title", None), "text", lambda: "")()
        for i in range(grid.count())
    ]
    assert any("Andamiaje" in t for t in titles), titles


def _scaffolding_titles(view):
    grid = view.cards_grid
    return [
        getattr(getattr(grid.itemAt(i).widget(), "title", None), "text", lambda: "")()
        for i in range(grid.count())
    ]


def test_review_then_back_returns_to_import_menu(main_window):
    """Regresión: tras pulsar «Revisar» el andamiaje y «Volver», se debe regresar
    al menú de importación con la tarjeta de andamiaje (aceptar/descartar), no
    quedarse con el cajón cerrado y sin forma de avanzar.

    El cajón NO apila contenido (``set_content`` destruye la vista anterior), así
    que el callback del panel debe reabrir el menú vía ``ctx.reopen_import``."""
    from hosts.DesktopHostPySide.views.import_export_view import ImportExportView
    from packages.domain.import_models import ImportBasket
    from packages.domain.project import Project

    win = main_window
    proj = Project(name="ReproVolver")
    proj.import_baskets = [ImportBasket(
        id="b-volver", source_id="s1", segments=[], import_candidates=[],
        review_state="pendiente", import_mode="canon",
        metadata={"project_config_suggestion": {
            "chronology": {"mode": "vague_periods", "eras": []},
            "world_layers": {"activate_default_layer_ids": [], "custom_layers": []},
            "milestones": [], "applied": False,
        }},
    )]
    win.controller.ps.active_project = proj

    win._import_document()
    view = win.import_export_view
    view_id_before = id(view)
    assert any("Andamiaje" in t for t in _scaffolding_titles(view))

    # «Revisar» monta el panel de configuración en el cajón (destruye la vista).
    view._open_config_panel("b-volver")
    panel = win.ctx.drawer._content
    assert panel is not None and hasattr(panel, "_finish")
    assert not isinstance(panel, ImportExportView)  # el panel reemplazó al menú

    # «Volver» (decisión "close") debe REABRIR el menú: una vista fresca montada en
    # el cajón con la tarjeta de andamiaje (no quedarse con el cajón cerrado).
    panel._finish("close")
    reopened = win.import_export_view
    assert id(reopened) != view_id_before               # se reconstruyó el menú
    assert isinstance(win.ctx.drawer._content, ImportExportView)  # montado en el cajón
    reopened_titles = _scaffolding_titles(reopened)
    assert any("Andamiaje" in t for t in reopened_titles), reopened_titles


def test_extraction_done_error_does_not_save(main_window, monkeypatch):
    win = main_window
    saves: list[bool] = []
    notes: list[tuple] = []
    monkeypatch.setattr(win, "_save_active_project_silent", lambda: saves.append(True) or True)
    win.ctx.notify_sink = lambda msg, kind="info": notes.append((msg, kind))

    win._on_import_extraction_done("b2", 0, "sin proveedor")

    assert saves == []                           # error → no autoguarda
    assert any(k == "error" for _m, k in notes)
