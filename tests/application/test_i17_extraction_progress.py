"""I17 — Extracción con progreso por segmento + cancelación (capa servicio).

El worker de la UI usa estos callbacks para "Analizando 3/12" + botón Cancelar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat, ImportMode
from packages.domain.project import Project
from packages.domain.result import unwrap
from packages.infrastructure.ai_provider import AIProvider


class _Provider(AIProvider):
    provider_name = "i17_fake"

    def __init__(self):
        self.call_count = 0

    def chat(self, system_prompt, user_message, timeout=None):
        self.call_count += 1
        return json.dumps({
            "candidates": [{"kind": "entity", "name": f"Ent{self.call_count}", "entity_type": "concepto"}]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i17.json")


def _service_with_doc(tmp_path, text):
    doc = tmp_path / "lore.txt"
    doc.write_text(text, encoding="utf-8")
    proj = Project(name="I17")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


@pytest.mark.application
def test_progress_callback_reaches_completion(tmp_path):
    # El progreso se reporta por VENTANA de extracción (I10), no por párrafo:
    # arranca en done=0 y termina en (total, total). Una llamada IA por ventana.
    svc, proj, doc = _service_with_doc(tmp_path, "Uno aqui.\n\nDos aqui.")
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))

    calls: list[tuple[int, int]] = []
    provider = _Provider()
    svc.extract_ai_candidates(
        basket.id, provider=provider, replace_existing=True,
        progress_callback=lambda done, total, label: calls.append((done, total)),
    )
    assert calls  # el callback se invoca
    total = calls[-1][1]
    assert total >= 1
    assert calls[0][0] == 0            # arranca en 0
    assert calls[-1] == (total, total)  # marca final = completado
    assert provider.call_count == total  # una llamada IA por ventana


@pytest.mark.application
def test_should_cancel_stops_before_extracting(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path, "Uno.\n\nDos.\n\nTres.")
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    provider = _Provider()

    cands = unwrap(svc.extract_ai_candidates(
        basket.id, provider=provider, replace_existing=True,
        should_cancel=lambda: True,
    ))
    # Cancelado antes del primer segmento: nada extraído, proveedor no llamado.
    assert cands == []
    assert provider.call_count == 0
