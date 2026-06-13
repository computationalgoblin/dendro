from __future__ import annotations

import json
from pathlib import Path

from packages.application.import_ai_extraction_service import ImportAIExtractionService
from packages.application.import_service import ImportService
from packages.domain.ai_models import AIResponse
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportReviewState
from packages.domain.project import Project
from packages.domain.result import Error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider


class I03Provider(AIProvider):
    provider_name = "i03_fake"

    def __init__(self, text: str | None = None):
        self.text = text
        self.calls: list[tuple[str, str, int | None]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        if self.text is not None:
            return self.text, None

        payload = json.loads(user_message)
        chunk = payload["chunk"]["text"]
        lower = chunk.lower()
        if "ambigua" in lower:
            return json.dumps({
                "candidates": [{
                    "kind": "import_issue",
                    "issue_type": "ambiguous_chunk",
                    "severity": "media",
                    "message": "El chunk menciona algo ambiguo sin referente claro.",
                    "confidence": 0.2,
                }]
            }, ensure_ascii=False), None
        if "batalla" in lower:
            return json.dumps({
                "candidates": [{
                    "kind": "milestone",
                    "title": "Batalla del Rio Gris",
                    "description": "La batalla cambio el equilibrio de poder.",
                    "date_label": "hace veinte anos",
                    "confidence": "high",
                }]
            }, ensure_ascii=False), None
        if "protege" in lower:
            return json.dumps({
                "candidates": [{
                    "kind": "relation",
                    "source_name": "Eldrin",
                    "target_name": "Torre de Marfil",
                    "relation_type": "protege",
                    "evidence": "Eldrin protege la Torre de Marfil.",
                    "confidence": 0.82,
                }]
            }, ensure_ascii=False), None
        if "faccion" in lower:
            return json.dumps({
                "candidates": [{
                    "kind": "branch",
                    "name": "Orden del Umbral",
                    "branch_type": "faccion",
                    "summary": "Faccion dedicada a custodiar portales.",
                    "member_entity_names": ["Eldrin"],
                    "confidence": 0.74,
                }]
            }, ensure_ascii=False), None
        return json.dumps({
            "candidates": [{
                "kind": "entity",
                "name": "Eldrin",
                "entity_type": "personaje",
                "aliases": ["El Mago del Norte"],
                "brief_description": "Personaje detectado en el chunk.",
                "confidence": 0.9,
            }]
        }, ensure_ascii=False), None

    def invoke(self, operation):  # pragma: no cover - I03 must use chat
        return AIResponse(id="i03", operation=operation, raw_text="", provider=self.provider_name)


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i03-project.json")


def _segment(text: str, *, segment_id: str = "seg-1") -> DocumentSegment:
    return DocumentSegment(
        id=segment_id,
        source_id="source-1",
        section="Capitulo",
        raw_text=text,
        start_offset=10,
        end_offset=10 + len(text),
        metadata={
            "chunk_id": f"{segment_id}-chunk",
            "chunk_order": 1,
            "file_name": "lore.md",
            "section_path": "Capitulo",
            "page_start": None,
            "page_end": None,
            "char_start": 10,
            "char_end": 10 + len(text),
            "extraction_method": "markdown",
        },
    )


def _extract_one(text: str):
    provider = I03Provider()
    service = ImportAIExtractionService(provider=provider)
    result = service.extract_from_segments([_segment(text)])
    assert is_ok(result)
    candidates = unwrap(result)
    assert provider.calls
    return candidates[0], provider


def test_i03_provider_extracts_entity_candidate_from_chunk():
    candidate, provider = _extract_one("Eldrin aparece como personaje central.")

    assert candidate.candidate_type == "entidad"
    assert candidate.review_state is ImportReviewState.PENDIENTE
    assert candidate.proposed_data["kind"] == "entity"
    assert candidate.proposed_data["name"] == "Eldrin"
    assert candidate.proposed_data["source_references"][0]["segment_id"] == "seg-1"
    assert "No inventes IDs" in provider.calls[0][0]
    assert provider.calls[0][2] == 300


def test_i03_provider_extracts_branch_candidate_from_faction_chunk():
    candidate, _ = _extract_one("La faccion Orden del Umbral custodia portales.")

    assert candidate.candidate_type == "entidad"
    assert candidate.proposed_data["kind"] == "branch"
    assert candidate.proposed_data["branch_type"] == "faccion"
    assert candidate.proposed_data["name"] == "Orden del Umbral"


def test_i03_provider_extracts_relation_candidate_from_explicit_relation():
    candidate, _ = _extract_one("Eldrin protege la Torre de Marfil.")

    assert candidate.candidate_type == "relacion"
    assert candidate.proposed_data["kind"] == "relation"
    assert candidate.proposed_data["source_name"] == "Eldrin"
    assert candidate.proposed_data["target_name"] == "Torre de Marfil"
    assert candidate.confidence == 0.82


def test_i03_provider_extracts_milestone_candidate_from_past_event():
    candidate, _ = _extract_one("La Batalla del Rio Gris ocurrio hace veinte anos.")

    assert candidate.candidate_type == "cambio"
    assert candidate.proposed_data["kind"] == "milestone"
    assert candidate.proposed_data["title"] == "Batalla del Rio Gris"
    assert candidate.confidence == 0.85


def test_i03_ambiguous_chunk_produces_import_issue():
    candidate, _ = _extract_one("Referencia ambigua sin sujeto claro.")

    assert candidate.candidate_type == "incidencia"
    assert candidate.proposed_data["kind"] == "import_issue"
    assert "ambiguo" in candidate.proposed_data["message"]


def test_i03_malformed_output_is_rejected_as_import_issue():
    provider = I03Provider(text="esto no es json")
    service = ImportAIExtractionService(provider=provider)

    result = service.extract_from_segments([_segment("Eldrin aparece.")])

    assert is_ok(result)
    candidate = unwrap(result)[0]
    assert candidate.candidate_type == "incidencia"
    assert candidate.review_state is ImportReviewState.RECHAZADO
    assert "malformado rechazado" in candidate.proposed_data["message"]


def test_i03_does_not_use_simulated_fallback_by_default():
    service = ImportAIExtractionService(provider=SimulatedAIProvider())

    result = service.extract_from_segments([_segment("Eldrin aparece.")])

    assert isinstance(result, Error)
    assert "contenido simulado" in result.error


def test_i03_import_service_appends_candidates_to_existing_basket():
    project = Project(name="I03")
    basket = ImportBasket(id="basket-1", source_id="source-1", segments=[_segment("Eldrin aparece.")])
    project.import_baskets.append(basket)
    service = ImportService(project_service=FakeProjectService(project))

    result = service.extract_ai_candidates("basket-1", provider=I03Provider())

    assert is_ok(result)
    assert len(basket.import_candidates) == 1
    assert basket.import_candidates[0].proposed_data["kind"] == "entity"
    assert basket.metadata["ai_extraction"]["provider"] == "i03_fake"

