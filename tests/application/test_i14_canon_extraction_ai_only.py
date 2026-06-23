"""I14 — Canon: extracción SOLO IA + bloqueo sin proveedor.

El import en modo canon ya no corre la heurística de palabras: el basket nace
vacío y la extracción rica es un paso explícito por IA. Sin proveedor IA real
(simulado, no permitido), la extracción se BLOQUEA con error claro en vez de
caer a heurística.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat, ImportMode
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider


class _RichProvider(AIProvider):
    provider_name = "i14_fake"

    def __init__(self):
        self.calls = []

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": "Eldrin",
                "entity_type": "personaje",
                "summary": "Mago anciano del Norte.",
                "body": "Eldrin custodia la Torre de Marfil desde hace décadas.",
                "confidence": 0.9,
            }]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i14.json")


def _service_with_doc(tmp_path, text="Eldrin es un mago. La Torre de Marfil brilla."):
    doc = tmp_path / "lore.txt"
    doc.write_text(text, encoding="utf-8")
    proj = Project(name="I14")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


@pytest.mark.application
def test_canon_import_does_not_run_heuristics(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    # Sin heurística: el basket canon nace vacío de candidatos.
    assert basket.import_candidates == []
    assert len(basket.segments) >= 1


@pytest.mark.application
def test_extraction_blocks_without_real_provider(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    # Proveedor simulado y no permitido → bloqueo, NO fallback heurístico.
    result = svc.extract_ai_candidates(
        basket.id, provider=SimulatedAIProvider(), allow_simulated=False
    )
    assert is_error(result)
    assert basket.import_candidates == []


@pytest.mark.application
def test_provider_resolved_from_environment(monkeypatch):
    # Regresión: la extracción creaba create_provider() sin args (default
    # "simulated"), ignorando la config del usuario. Ahora lee NARRATIVE_AI_*.
    from packages.application.import_ai_extraction_service import resolve_configured_provider

    for var in ("NARRATIVE_AI_PROVIDER", "NARRATIVE_AI_BASE_URL", "NARRATIVE_AI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert resolve_configured_provider().provider_name == "simulated"

    monkeypatch.setenv("NARRATIVE_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NARRATIVE_AI_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("NARRATIVE_AI_API_KEY", "test-key")
    assert resolve_configured_provider().provider_name != "simulated"


@pytest.mark.application
def test_extraction_with_real_provider_yields_rich_candidates(tmp_path):
    svc, proj, doc = _service_with_doc(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    provider = _RichProvider()
    result = svc.extract_ai_candidates(basket.id, provider=provider, replace_existing=True)
    assert is_ok(result)
    cands = unwrap(result)
    assert len(cands) >= 1
    payload = cands[0].proposed_data
    # Candidato rico: resumen + cuerpo, no solo el nombre.
    assert payload.get("summary")
    assert payload.get("body")
    # Importar/extraer nunca escribe canon.
    assert proj.entities == []
