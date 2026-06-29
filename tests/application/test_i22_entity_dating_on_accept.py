"""I22 — Fase 2: las entidades se datan y clasifican al aceptarse.

Tras aplicar el andamiaje (calendario + anillos), la extracción contextualizada
propone entidades con span existencial (birth/death/nature) y pertenencia causal
(layer_ids). Al aceptar el candidato, esos campos se materializan en la entidad de
canon: ``life_span`` datado y ``layer_ids`` poblado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat, ImportMode
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap
from packages.domain.world_layer import default_world_layers
from packages.infrastructure.ai_provider import AIProvider


class _DatedEntityProvider(AIProvider):
    provider_name = "i22_fake"

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": "Rodrigo",
                "entity_type": "personaje",
                "body": "Último rey godo.",
                "birth_year": 688,
                "death_year": 711,
                "temporal_nature": "mortal",
                "layer_ids": ["layer_historia"],
                "confidence": 0.9,
            }]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i22.json")


def _service(tmp_path):
    proj = Project(name="I22")
    # El andamiaje ya está aplicado: existe la capa causal de historia.
    proj.world_layers.append(
        next(wl for wl in default_world_layers() if wl.id == "layer_historia")
    )
    doc = tmp_path / "alandalus.txt"
    doc.write_text("Don Rodrigo reinó hasta la conquista en 711.", encoding="utf-8")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


@pytest.mark.application
def test_accepted_entity_is_dated_and_classified(tmp_path):
    svc, proj, doc = _service(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = unwrap(
        svc.extract_ai_candidates(basket.id, provider=_DatedEntityProvider(), replace_existing=True)
    )
    rodrigo = next(c for c in cands if (c.proposed_data or {}).get("name") == "Rodrigo")
    # El candidato lleva la datación y la pertenencia causal propuestas.
    assert rodrigo.proposed_data["birth_year"] == 688
    assert rodrigo.proposed_data["layer_ids"] == ["layer_historia"]

    result = svc.apply_import_candidate_to_canon(basket.id, rodrigo.id)
    assert is_ok(result)
    entity = next(e for e in proj.entities if e.name == "Rodrigo")
    # Span existencial datado contra el eje del mundo.
    span = entity.as_temporal_span()
    assert entity.birth_year == 688
    assert entity.death_year == 711
    assert span.is_dated()
    # Pertenencia causal asignada al anillo.
    assert "layer_historia" in (entity.layer_ids or [])
