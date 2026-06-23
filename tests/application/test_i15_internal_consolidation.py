"""I15 — Consolidación interna: la IA no ofrece el mismo candidato N veces.

Tras extraer por segmentos, los candidatos equivalentes (mismo nombre/alias) se
fusionan in situ en UN candidato enriquecido ANTES de presentarse. Los originales
quedan FUSIONADO.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat, ImportMode, ImportReviewState
from packages.domain.project import Project
from packages.domain.result import unwrap
from packages.infrastructure.ai_provider import AIProvider


class _DupProvider(AIProvider):
    """Emite un único 'Eldrin' por llamada (sin duplicados internos)."""

    provider_name = "i15_fake"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": "Eldrin",
                "entity_type": "personaje",
                "summary": "Mago anciano.",
                "confidence": 0.9,
            }]
        }, ensure_ascii=False), None


class _DoubleDupProvider(AIProvider):
    """Emite DOS 'Eldrin' equivalentes en una respuesta → duplicados a consolidar.

    Robusto al troceado/ventaneo: la consolidación opera sobre candidatos
    equivalentes, no sobre el número de segmentos.
    """

    provider_name = "i15_double"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({
            "candidates": [
                {"kind": "entity", "name": "Eldrin", "entity_type": "personaje",
                 "summary": "Mago anciano.", "confidence": 0.9},
                {"kind": "entity", "name": "Eldrin", "entity_type": "personaje",
                 "summary": "El mismo mago, otra mención.", "confidence": 0.8},
            ]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i15.json")


def _service_with_doc(tmp_path, text):
    doc = tmp_path / "lore.txt"
    doc.write_text(text, encoding="utf-8")
    proj = Project(name="I15")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


@pytest.mark.application
def test_duplicate_candidates_are_consolidated(tmp_path):
    # La IA propone dos 'Eldrin' equivalentes → deben consolidarse en uno.
    svc, proj, doc = _service_with_doc(tmp_path, "Eldrin aparece aqui. Eldrin tambien aqui.")
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))

    cands = unwrap(svc.extract_ai_candidates(basket.id, provider=_DoubleDupProvider(), replace_existing=True))

    # Presentables: un único Eldrin consolidado (con merged_from).
    eldrins = [c for c in cands if (c.proposed_data or {}).get("name") == "Eldrin"]
    assert len(eldrins) == 1
    assert eldrins[0].proposed_data.get("merged_from")
    # Los candidatos originales quedan FUSIONADO en el basket (no se presentan).
    fused = [c for c in basket.import_candidates if c.review_state == ImportReviewState.FUSIONADO]
    assert len(fused) == 2
    assert eldrins[0] not in fused


@pytest.mark.application
def test_distinct_candidates_are_not_merged(tmp_path):
    # Un solo segmento con un único nombre → nada que consolidar.
    svc, proj, doc = _service_with_doc(tmp_path, "Eldrin es un mago.")
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = unwrap(svc.extract_ai_candidates(basket.id, provider=_DupProvider(), replace_existing=True))
    eldrins = [c for c in cands if (c.proposed_data or {}).get("name") == "Eldrin"]
    assert len(eldrins) == 1
    # Sin duplicados, no hay merged_from.
    assert not eldrins[0].proposed_data.get("merged_from")
