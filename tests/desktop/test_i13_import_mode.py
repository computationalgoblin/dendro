"""I13 — UI: el ImportController reenvía el modo al servicio.

El selector de modo de la vista (canon/contexto) llega hasta ImportService vía
el controller, sin que la UI escriba en persistencia directamente.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i13.json")


def _controller_with_doc(tmp_path, text="Eldrin es un mago.\n\nLa Torre brilla."):
    doc = tmp_path / "lore.txt"
    doc.write_text(text, encoding="utf-8")
    proj = Project(name="I13")
    ctrl = ImportController(project_service=FakeProjectService(proj))
    return ctrl, proj, doc


def test_controller_defaults_to_canon(tmp_path):
    ctrl, proj, doc = _controller_with_doc(tmp_path)
    result = ctrl.import_document(str(doc))
    assert is_ok(result)
    assert unwrap(result).import_mode == "canon"


def test_controller_forwards_contexto_mode(tmp_path):
    ctrl, proj, doc = _controller_with_doc(tmp_path)
    result = ctrl.import_document(str(doc), mode="contexto")
    assert is_ok(result)
    basket = unwrap(result)
    assert basket.import_mode == "contexto"
    # Modo contexto: sin candidatos de canon.
    assert basket.import_candidates == []
    # La importación nunca escribe canon.
    assert proj.entities == []
