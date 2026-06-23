"""I11 — Extracción dirigida por taxonomía + Ring end-to-end.

La extracción IA del Modo Canon recibe la taxonomía del proyecto (qué
entity_type/branch_type/anillos son válidos) y un resumen del canon. Valida los
candidatos contra la taxonomía (strict → RECHAZADO, permisivo → incidencia
PENDIENTE). ring_suggestion se mapea a CandidateType.ANILLO y se materializa
como WorldLayer al aceptar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.application.prompt_registry import get_prompt
from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import (
    DocumentSegment,
    ImportBasket,
    ImportReviewState,
)
from packages.domain.project import Project, ProjectTaxonomy
from packages.domain.result import is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


class FixedProvider(AIProvider):
    """Provider que devuelve un payload fijo y registra el system prompt."""

    provider_name = "i11_fake"

    def __init__(self, candidates: list[dict]):
        self._candidates = candidates
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        return json.dumps({"candidates": self._candidates}, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i11.json")


def _project_with_basket(taxonomy: ProjectTaxonomy | None = None) -> tuple[Project, str]:
    proj = Project(name="I11")
    if taxonomy is not None:
        proj.import_taxonomy = taxonomy
    seg = DocumentSegment(id="seg-1", source_id="src-1", section="Lore", raw_text="texto")
    basket = ImportBasket(id="bsk-1", source_id="src-1", segments=[seg], import_candidates=[])
    proj.import_baskets = [basket]
    return proj, basket.id


def _extract(proj, basket_id, provider):
    svc = ImportService(project_service=FakeProjectService(proj))
    return svc.extract_ai_candidates(basket_id, provider=provider)


@pytest.mark.application
def test_prompt_lives_in_registry():
    assert get_prompt("import_extraction", "es") is not None
    assert "JSON" in get_prompt("import_extraction", "es")


@pytest.mark.application
def test_taxonomy_injected_into_system_prompt():
    tax = ProjectTaxonomy(allowed_entity_types=["personaje"], extraction_guidance="solo el núcleo")
    proj, bid = _project_with_basket(tax)
    provider = FixedProvider([{"kind": "entity", "name": "Eldrin", "entity_type": "personaje"}])
    _extract(proj, bid, provider)
    system_prompt = provider.calls[0][0]
    assert "TAXONOMIA DEL PROYECTO" in system_prompt
    assert "personaje" in system_prompt
    assert "solo el núcleo" in system_prompt


@pytest.mark.application
def test_ring_suggestion_maps_to_anillo():
    proj, bid = _project_with_basket()
    provider = FixedProvider([
        {"kind": "ring_suggestion", "ring_name": "Estrato Onírico", "description": "Capa causal."}
    ])
    result = _extract(proj, bid, provider)
    cands = unwrap(result)
    assert len(cands) == 1
    assert cands[0].candidate_type == CandidateType.ANILLO.value


@pytest.mark.application
def test_out_of_taxonomy_strict_is_rejected():
    tax = ProjectTaxonomy(allowed_entity_types=["personaje"], strict=True)
    proj, bid = _project_with_basket(tax)
    provider = FixedProvider([{"kind": "entity", "name": "Dragón", "entity_type": "criatura"}])
    cands = unwrap(_extract(proj, bid, provider))
    assert len(cands) == 1
    assert cands[0].review_state == ImportReviewState.RECHAZADO
    assert cands[0].candidate_type == CandidateType.INCIDENCIA.value


@pytest.mark.application
def test_out_of_taxonomy_permissive_is_pending_issue():
    tax = ProjectTaxonomy(allowed_entity_types=["personaje"], strict=False)
    proj, bid = _project_with_basket(tax)
    provider = FixedProvider([{"kind": "entity", "name": "Dragón", "entity_type": "criatura"}])
    cands = unwrap(_extract(proj, bid, provider))
    assert len(cands) == 1
    assert cands[0].review_state == ImportReviewState.PENDIENTE
    assert cands[0].candidate_type == CandidateType.INCIDENCIA.value


@pytest.mark.application
def test_in_taxonomy_candidate_passes():
    tax = ProjectTaxonomy(allowed_entity_types=["personaje"], strict=True)
    proj, bid = _project_with_basket(tax)
    provider = FixedProvider([{"kind": "entity", "name": "Eldrin", "entity_type": "personaje"}])
    cands = unwrap(_extract(proj, bid, provider))
    assert cands[0].review_state == ImportReviewState.PENDIENTE
    assert cands[0].candidate_type == CandidateType.ENTIDAD.value


@pytest.mark.application
def test_ring_candidate_applies_to_canon_as_world_layer():
    proj, bid = _project_with_basket()
    provider = FixedProvider([
        {"kind": "ring_suggestion", "ring_name": "Estrato Onírico", "description": "Capa causal."}
    ])
    svc = ImportService(project_service=FakeProjectService(proj))
    cands = unwrap(svc.extract_ai_candidates(bid, provider=provider))
    ring_cand = cands[0]
    rings_before = len(proj.world_layers)

    result = svc.apply_import_candidate_to_canon(bid, ring_cand.id)

    assert is_ok(result)
    assert len(proj.world_layers) == rings_before + 1
    assert proj.world_layers[-1].name == "Estrato Onírico"
    assert ring_cand.review_state == ImportReviewState.ACEPTADO
