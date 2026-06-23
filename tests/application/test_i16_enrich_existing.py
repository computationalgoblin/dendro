"""I16 — Cruce con el canon: enriquecer en vez de duplicar.

Si un candidato coincide con una entidad ya existente en el canon, se marca
``enrich_target_id`` y, al aceptar, se enriquece esa entidad (une aliases,
completa cuerpo si está vacío) sin crear un duplicado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.import_models import ImportFormat, ImportMode
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


class _EldrinProvider(AIProvider):
    provider_name = "i16_fake"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": "Eldrin",
                "entity_type": "personaje",
                "aliases": ["El Mago del Norte"],
                "body": "Custodio de la Torre de Marfil.",
                "confidence": 0.9,
            }]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i16.json")


def _service_with_canon_eldrin(tmp_path):
    proj = Project(name="I16")
    proj.entities = [
        NarrativeEntity(id="ent-eldrin", name="Eldrin", entity_type=EntityType.PERSONAJE)
    ]
    doc = tmp_path / "lore.txt"
    doc.write_text("Eldrin protege la Torre.", encoding="utf-8")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


@pytest.mark.application
def test_candidate_matching_canon_is_marked_enrich(tmp_path):
    svc, proj, doc = _service_with_canon_eldrin(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = unwrap(svc.extract_ai_candidates(basket.id, provider=_EldrinProvider(), replace_existing=True))
    eldrin = next(c for c in cands if (c.proposed_data or {}).get("name") == "Eldrin")
    assert eldrin.proposed_data.get("enrich_target_id") == "ent-eldrin"
    assert eldrin.proposed_data.get("presentation_kind") == "enrich_existing"


@pytest.mark.application
def test_accepting_enrich_updates_existing_not_duplicate(tmp_path):
    svc, proj, doc = _service_with_canon_eldrin(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = unwrap(svc.extract_ai_candidates(basket.id, provider=_EldrinProvider(), replace_existing=True))
    eldrin = next(c for c in cands if (c.proposed_data or {}).get("name") == "Eldrin")

    before = len(proj.entities)
    result = svc.apply_import_candidate_to_canon(basket.id, eldrin.id)
    assert is_ok(result)

    # No se crea duplicado: sigue habiendo una sola entidad.
    assert len(proj.entities) == before
    target = proj.entities[0]
    # Alias del candidato se fusiona en la entidad existente.
    assert "El Mago del Norte" in (target.aliases or [])
    # Cuerpo vacío se completa.
    assert "Torre de Marfil" in (target.extended_description or "")
