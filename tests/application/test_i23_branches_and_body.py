"""I23 — Importación: ramas (membresía + anidamiento) y cuerpo de entidades.

Cubre los dos huecos detectados tras I22/UX33:

1. Las hojas extraídas deben traer CUERPO (``extended_description``): el prompt v3 lo
   exige y el mapeo ``body → extended_description`` ya existía.
2. Una pasada de agrupación a nivel documento (Fase 3) propone RAMAS, con qué entidades
   contienen y su anidamiento, expandiéndose en candidatos ``branch`` + relaciones
   ``contiene`` revisables (rama→miembro y rama→subrama). Al aceptar, la rama es una
   entidad contenedora y la membresía/anidamiento se materializan como relaciones
   ``contiene`` resueltas por nombre.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.import_ai_extraction_service import ImportAIExtractionService
from packages.application.import_service import ImportService
from packages.domain.candidate_issue import CandidateType
from packages.domain.import_models import (
    ImportBasket,
    ImportCandidate,
    ImportFormat,
    ImportMode,
    ImportReviewState,
)
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider

# ── Providers fake ───────────────────────────────────────────────────────────

class _ExtractAndGroupProvider(AIProvider):
    """Responde según la intención (mismo provider para extracción y agrupación):

    - extracción (``extract_reviewable_import_candidates``) → hojas con cuerpo.
    - agrupación (``group_entities_into_branches``) → ramas con membresía y anidamiento.
    """

    provider_name = "i23_fake"

    def chat(self, system_prompt, user_message, timeout=None):
        if "group_entities_into_branches" in user_message:
            return json.dumps({
                "branches": [
                    {
                        "name": "Reino Visigodo",
                        "branch_type": "institucion",
                        "body": "Estado godo de la península antes de 711.",
                        "members": ["Rodrigo"],
                        "parent": None,
                    },
                    {
                        "name": "Casa Real",
                        "branch_type": "faccion",
                        "body": "Linaje gobernante del reino.",
                        "members": ["Rodrigo"],
                        "parent": "Reino Visigodo",
                    },
                ]
            }, ensure_ascii=False), None
        return json.dumps({
            "candidates": [
                {
                    "kind": "entity",
                    "name": "Rodrigo",
                    "entity_type": "personaje",
                    "body": "Último rey godo, derrotado en la conquista de 711.",
                    "confidence": 0.9,
                },
                {
                    "kind": "entity",
                    "name": "Táriq",
                    "entity_type": "personaje",
                    "body": "Comandante que cruzó el estrecho en 711.",
                    "confidence": 0.9,
                },
            ]
        }, ensure_ascii=False), None


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i23.json")


def _service(tmp_path):
    proj = Project(name="I23")
    doc = tmp_path / "alandalus.txt"
    doc.write_text("Don Rodrigo reinó hasta la conquista de Táriq en 711.", encoding="utf-8")
    svc = ImportService(project_service=FakeProjectService(proj, tmp_path / "p.json"))
    return svc, proj, doc


def _is_contiene(rel) -> bool:
    return "contiene" in str(getattr(rel, "relation_type", "")).lower()


def _extract(svc, basket):
    return unwrap(svc.extract_ai_candidates(
        basket.id, provider=_ExtractAndGroupProvider(), replace_existing=True
    ))


# ── 1. Cuerpo ────────────────────────────────────────────────────────────────

@pytest.mark.application
def test_accepted_entity_has_body(tmp_path):
    svc, proj, doc = _service(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = _extract(svc, basket)
    rodrigo = next(c for c in cands if (c.proposed_data or {}).get("name") == "Rodrigo")
    assert rodrigo.proposed_data.get("body")  # el cuerpo viaja en el candidato

    assert is_ok(svc.apply_import_candidate_to_canon(basket.id, rodrigo.id))
    entity = next(e for e in proj.entities if e.name == "Rodrigo")
    assert entity.extended_description.startswith("Último rey godo")


# ── 2. La Fase 3 añade ramas + relaciones contiene ───────────────────────────

@pytest.mark.application
def test_grouping_adds_branch_and_contiene_candidates(tmp_path):
    svc, proj, doc = _service(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = _extract(svc, basket)

    branches = [c for c in cands if (c.proposed_data or {}).get("kind") == "branch"]
    contiene = [
        c for c in cands
        if (c.proposed_data or {}).get("relation_type") == "contiene"
    ]
    branch_names = {(c.proposed_data or {}).get("name") for c in branches}
    assert {"Reino Visigodo", "Casa Real"} <= branch_names
    # Membresía rama→miembro y anidamiento rama→subrama.
    pairs = {
        ((c.proposed_data or {}).get("source_name"), (c.proposed_data or {}).get("target_name"))
        for c in contiene
    }
    assert ("Reino Visigodo", "Rodrigo") in pairs       # miembro
    assert ("Reino Visigodo", "Casa Real") in pairs     # anidamiento (parent)


# ── 3. Aceptar materializa contenedor + membresía como relación contiene ──────

@pytest.mark.application
def test_accept_branch_and_member_creates_container_and_containment(tmp_path):
    svc, proj, doc = _service(tmp_path)
    basket = unwrap(svc.import_document(doc, ImportFormat.TEXT_PLAIN, mode=ImportMode.CANON))
    cands = _extract(svc, basket)

    def _accept(pred):
        for c in cands:
            if pred(c):
                assert is_ok(svc.apply_import_candidate_to_canon(basket.id, c.id)), c.proposed_data

    # Orden: entidades/ramas primero, relaciones después (resolución por nombre).
    _accept(lambda c: (c.proposed_data or {}).get("name") == "Rodrigo"
            and (c.proposed_data or {}).get("kind") == "entity")
    _accept(lambda c: (c.proposed_data or {}).get("name") == "Reino Visigodo")
    _accept(lambda c: (c.proposed_data or {}).get("relation_type") == "contiene"
            and (c.proposed_data or {}).get("source_name") == "Reino Visigodo"
            and (c.proposed_data or {}).get("target_name") == "Rodrigo")

    reino = next(e for e in proj.entities if e.name == "Reino Visigodo")
    rodrigo = next(e for e in proj.entities if e.name == "Rodrigo")
    # Es una rama (contenedor) con cuerpo.
    assert (reino.custom_metadata or {}).get("display_type") == "rama"
    assert reino.extended_description
    # La membresía es una relación contiene rama→miembro.
    rel = next(r for r in proj.relations if _is_contiene(r))
    assert rel.source_id == reino.id and rel.target_id == rodrigo.id


# ── 4. Degradación sin proveedor / sin entidades ─────────────────────────────

@pytest.mark.application
def test_grouping_degrades_without_provider():
    # Simulado y sin allow_simulated → Error claro, no candidatos falsos.
    svc = ImportAIExtractionService(provider=None, allow_simulated=False)
    svc.provider = _Simulated()
    basket = ImportBasket(id="b1", source_id="s1")
    res = svc.propose_branches_for_basket(basket)
    assert is_error(res)


@pytest.mark.application
def test_grouping_no_entities_returns_empty():
    svc = ImportAIExtractionService(provider=_ExtractAndGroupProvider())
    basket = ImportBasket(id="b2", source_id="s2")  # sin candidatos de entidad
    res = svc.propose_branches_for_basket(basket)
    assert is_ok(res) and unwrap(res) == []


# ── 5. Expansión directa: dedupe de contiene + anidamiento ───────────────────

@pytest.mark.application
def test_expand_dedupes_and_nests():
    svc = ImportAIExtractionService(provider=_ExtractAndGroupProvider())
    basket = ImportBasket(id="b3", source_id="s3")
    for name in ("Rodrigo", "Táriq"):
        basket.import_candidates.append(ImportCandidate(
            id=name, candidate_type=CandidateType.ENTIDAD.value,
            proposed_data={"kind": "entity", "name": name, "body": "x"},
            review_state=ImportReviewState.PENDIENTE,
        ))
    added = unwrap(svc.propose_branches_for_basket(basket))
    branches = [c for c in added if c.candidate_type == CandidateType.ENTIDAD.value]
    relations = [c for c in added if c.candidate_type == CandidateType.RELACION.value]
    assert len(branches) == 2  # Reino Visigodo + Casa Real
    # contiene esperadas: Reino→Rodrigo, Casa Real→Rodrigo, Reino→Casa Real (parent),
    # sin duplicados.
    pairs = sorted(
        (c.proposed_data["source_name"], c.proposed_data["target_name"]) for c in relations
    )
    assert pairs == sorted([
        ("Reino Visigodo", "Rodrigo"),
        ("Casa Real", "Rodrigo"),
        ("Reino Visigodo", "Casa Real"),
    ])


class _Simulated(AIProvider):
    provider_name = "simulated"

    def chat(self, system_prompt, user_message, timeout=None):
        return "{}", None
