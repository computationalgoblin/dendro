"""BETA2-MEM-10: visor editorial de Memoria en Configuración (offscreen)."""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.narrative_memory_service import NarrativeMemoryService  # noqa: E402
from packages.domain.narrative_memory import MemoryTargetKind  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


@dataclass
class _FakeProjectService:
    active_project: Project = None


class _StubMemoryAI:
    """Regeneración IA: stagea una propuesta (el pipeline real se prueba en MEM-05)."""

    def __init__(self, mem):
        self.mem = mem

    def update_memory(self, kind, tid, ctx="", *, mode="regen"):
        return self.mem.stage_revision_proposal(
            kind, tid, ctx, after={"resumen_editorial": "nuevo por IA"}, motivo="regen"
        )


def _setup():
    ps = _FakeProjectService(active_project=Project(id="p", name="P"))
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.PROJECT, "", resumen_editorial="Resumen global.")
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="Ana, reina.")
    return ps, mem


def test_viewer_lists_and_edits(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    ps, mem = _setup()
    panel = MemoryViewerPanel(mem)
    assert panel.list.count() == 2
    panel.list.setCurrentRow(1)  # entity:e1
    assert "Ana" in panel.resumen.toPlainText()
    panel.resumen.setPlainText("Ana, reina exiliada (editado).")
    panel._save()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial.endswith("(editado).")


def test_viewer_delete(qapp, monkeypatch):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    ps, mem = _setup()
    panel = MemoryViewerPanel(mem)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    panel.list.setCurrentRow(1)
    panel._delete()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value is None
    assert panel.list.count() == 1


def test_viewer_regenerate_shows_diff_and_accepts(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    ps, mem = _setup()
    panel = MemoryViewerPanel(mem, memory_ai_service=_StubMemoryAI(mem))
    panel.list.setCurrentRow(1)
    panel._regenerate()
    assert not panel.accept_btn.isHidden()  # propuesta pendiente → diff visible
    # el contenido NO se ha sustituido aún
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial == "Ana, reina."
    panel._accept_proposal()
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial == "nuevo por IA"


def test_viewer_regenerate_disabled_without_ai(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    _, mem = _setup()
    panel = MemoryViewerPanel(mem)  # sin memory_ai_service
    assert not panel.regen_btn.isEnabled()  # leer/editar/borrar siguen; regenerar no
