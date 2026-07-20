"""BETA2-MEM-09: sección de Memoria en Cultivo (offscreen) + resolve_issue."""

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
from packages.domain.narrative_memory import (  # noqa: E402
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryIssueStatus,
    MemoryTargetKind,
    NarrativeMemory,
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


def _block(freshness=MemoryFreshness.FALTA_REGAR):
    return NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id="e1",
        resumen_editorial="Ana, reina exiliada.",
        freshness=freshness,
        issues=[MemoryIssue(id="iss1", kind=MemoryIssueKind.CONTRADICCION, texto="Muere y revive")],
    )


def test_memory_section_renders_block(qapp):
    from hosts.DesktopHostPySide.widgets.foco.memory_section import MemorySection

    sec = MemorySection()
    sec.render(_block())
    assert "Falta regar" in sec.freshness_chip.text()
    assert "Ana" in sec.summary.text()
    assert not sec.aviso.isHidden()  # obsoleta → aviso (offscreen: usar isHidden)
    assert sec._issues_box.count() == 1  # la contradicción abierta se muestra


def test_memory_section_none_shows_empty(qapp):
    from hosts.DesktopHostPySide.widgets.foco.memory_section import MemorySection

    sec = MemorySection()
    sec.render(None)
    assert "Sin memoria" in sec.freshness_chip.text()
    assert sec._issues_box.count() == 0


def test_memory_section_emits_issue_action(qapp):
    from hosts.DesktopHostPySide.widgets.foco.memory_section import MemorySection

    sec = MemorySection()
    sec.render(_block())
    seen = []
    sec.issueAction.connect(lambda iid, st: seen.append((iid, st)))
    sec.issueAction.emit("iss1", "aceptada")  # simula clic en «Aceptar»
    assert seen == [("iss1", "aceptada")]


def test_cultivation_notebook_hosts_memory_section(qapp):
    from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import CultivationNotebook

    nb = CultivationNotebook()
    nb.set_entity("e1")
    forwarded = []
    nb.memoryIssueAction.connect(lambda eid, iid, st: forwarded.append((eid, iid, st)))
    nb.set_memory_provider(lambda entity_id: _block())
    assert "Falta regar" in nb.memory_section.freshness_chip.text()
    nb.memory_section.issueAction.emit("iss1", "corregida")
    assert forwarded == [("e1", "iss1", "corregida")]


def test_resolve_issue_service():
    """El host aplica la acción del widget vía NarrativeMemoryService.resolve_issue."""
    ps = _FakeProjectService(active_project=Project(id="p", name="P"))
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(
        MemoryTargetKind.ENTITY, "e1",
        issues=[MemoryIssue(id="iss1", kind=MemoryIssueKind.HUECO, texto="falta algo")],
    )
    res = mem.resolve_issue(
        MemoryTargetKind.ENTITY, "e1", issue_id="iss1", status=MemoryIssueStatus.APLAZADA
    )
    assert isinstance(res, Ok)
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block.issues[0].estado == MemoryIssueStatus.APLAZADA
