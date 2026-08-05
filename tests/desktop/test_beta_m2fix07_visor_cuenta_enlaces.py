"""BETA-MULTIAGENT2-FIX-07 (criterio 4): lo descartado no se pierde en silencio.

La app resuelve los enlaces de la página contra el canon antes de persistirlos y tira
los que no existen. Ese descarte se DICE en la cabecera del visor — la lección de G2-03
es que lo que se cae callando se convierte en una mentira silenciosa.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.narrative_memory_service import NarrativeMemoryService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.narrative_memory import (  # noqa: E402
    MemoryCitation,
    MemoryTargetKind,
)
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
    """Devuelve el `Ok` que devuelve `MemoryAIService.update_memory` tras FIX-07."""

    def __init__(self, mem, refs):
        self.mem = mem
        self.refs = refs

    def update_memory(self, kind, tid, ctx="", *, mode="regen"):
        res = self.mem.upsert_memory(
            kind,
            tid,
            ctx,
            resumen_editorial="Ana, reina.",
            wikilinks=[MemoryCitation(MemoryTargetKind.ENTITY, "e2")],
        )
        return Ok({"applied": True, "block": res.value, "refs": dict(self.refs)})


def _setup():
    proj = Project(id="p", name="P")
    proj.entities.append(NarrativeEntity(id="e1", name="Ana"))
    proj.entities.append(NarrativeEntity(id="e2", name="Beto"))
    ps = _FakeProjectService(active_project=proj)
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="Ana, reina.")
    return ps, mem


def _regenerar(panel, qapp):
    panel.list.setCurrentRow(0)
    panel._regenerate()
    worker = panel._regen_worker
    assert worker is not None
    assert worker.wait(5000), "el worker de regeneración no terminó a tiempo"
    for _ in range(20):
        qapp.processEvents()
        if panel._regen_worker is None:
            break


def test_beta_m2fix07_el_visor_cuenta_los_enlaces_de_la_pagina(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    _, mem = _setup()
    panel = MemoryViewerPanel(mem)
    panel.list.setCurrentRow(0)

    # Antes de FIX-07 lo único que se decía de los enlaces era «Fuentes: N».
    assert "Enlaces: 0" in panel.freshness.text()


def test_beta_m2fix07_el_visor_dice_cuantos_enlaces_se_cayeron(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    _, mem = _setup()
    refs = {"resueltos": 1, "ambiguos": 2, "descartados": 3}
    panel = MemoryViewerPanel(mem, memory_ai_service=_StubMemoryAI(mem, refs))

    _regenerar(panel, qapp)

    texto = panel.freshness.text()
    assert "Enlaces: 1" in texto
    assert "3 sin elemento en el canon" in texto
    assert "2 con nombre duplicado" in texto


def test_beta_m2fix07_sin_descartes_no_se_da_la_lata(qapp):
    from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel

    _, mem = _setup()
    refs = {"resueltos": 4, "ambiguos": 0, "descartados": 0}
    panel = MemoryViewerPanel(mem, memory_ai_service=_StubMemoryAI(mem, refs))

    _regenerar(panel, qapp)

    assert "descartados" not in panel.freshness.text()
    assert "Enlaces: 1" in panel.freshness.text()
