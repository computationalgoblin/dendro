"""I09 — Bifurcación de import_document() por modo (canon / contexto).

Modo CANON conserva el flujo histórico (extrae candidatos heurísticos). Modo
CONTEXTO no genera candidatos de canon: los segmentos quedan como material de
referencia. El modo se espeja en basket.import_mode y en metadata.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat, ImportMode
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/test.json")


def _service_with_doc(tmp_path, text):
    doc_path = tmp_path / "lore.txt"
    doc_path.write_text(text, encoding="utf-8")
    proj = Project(name="Test")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc_path


_LORE = "Eldrin es un mago anciano.\n\nLa Torre de Marfil brilla en la noche."


@pytest.mark.application
def test_default_mode_is_canon(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, _LORE)
    result = svc.import_document(doc, ImportFormat.TEXT_PLAIN)
    assert is_ok(result)
    basket = unwrap(result)
    assert basket.import_mode == "canon"
    assert basket.metadata["import_mode"] == "canon"


@pytest.mark.application
def test_canon_mode_basket_starts_empty(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, _LORE)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    # I14: el import canon ya NO corre la heurística; el basket nace vacío y la
    # extracción IA rica es un paso explícito posterior (extract_ai_candidates).
    assert basket.import_mode == "canon"
    assert basket.import_candidates == []
    assert len(basket.segments) >= 1


@pytest.mark.application
def test_contexto_mode_produces_no_candidates(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, _LORE)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CONTEXTO))
    assert basket.import_mode == "contexto"
    assert basket.metadata["import_mode"] == "contexto"
    # Modo contexto NUNCA propone candidatos de canon...
    assert basket.import_candidates == []
    # ...pero conserva los segmentos para indexar como referencia.
    assert len(basket.segments) >= 1


@pytest.mark.application
def test_both_modes_register_source_and_basket(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, _LORE)
    svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CONTEXTO)
    assert len(proj.sources) == 1
    assert proj.sources[0].source_type.value == "documento_importado"
    assert len(proj.import_baskets) == 1


@pytest.mark.application
def test_contexto_mode_never_writes_canon(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, _LORE)
    svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CONTEXTO)
    # Importar (en cualquier modo) no muta canon.
    assert proj.entities == []
    assert proj.relations == []
