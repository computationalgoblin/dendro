"""I13 — aplicar la propuesta de config de proyecto (acción explícita).

Aceptar aplica el calendario (apply_candidate), ubica las entidades en el tiempo
(mergea birth/death/nature en sus candidatos) y aplica la taxonomía. Antes de
aceptar no se aplica nada. Nunca escribe canon directamente.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap


class FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i13.json")


def _proposal():
    return {
        "chronology": {
            "mode": "vague_periods",
            "calendar_name": "Eras del Norte",
            "present_year": 1200,
            "supports_exact_dates": False,
            "eras": [
                {"name": "Antigua", "start_year": 0, "end_year": 800, "description": "Mítica."},
                {"name": "Reciente", "start_year": 801, "end_year": None, "description": "Hoy."},
            ],
        },
        "entity_temporal": [
            {"name": "Eldrin", "birth_year": 900, "death_year": 1180,
             "nature": "mortal", "note": ""},
        ],
        "config": {
            "tone": "épico", "genre": "fantasía",
            "taxonomy": {"allowed_entity_types": ["personaje"], "allowed_branch_types": [],
                         "extraction_guidance": "núcleo"},
        },
        "applied": False,
    }


def _entity_candidate(name="Eldrin"):
    return ImportCandidate(
        id=f"cand-{name}", segment_id="seg-1", candidate_type="entidad",
        proposed_data={"kind": "entity", "name": name, "summary": "x"},
        review_state=ImportReviewState.PENDIENTE,
    )


def _service_with_proposal():
    proj = Project(name="I13")
    cand = _entity_candidate()
    basket = ImportBasket(id="b1", source_id="s1", segments=[], import_candidates=[cand],
                          review_state="pendiente", import_mode="canon",
                          metadata={"project_config_suggestion": _proposal()})
    proj.import_baskets = [basket]
    svc = ImportService(project_service=FakeProjectService(proj))
    return svc, proj, basket, cand


@pytest.mark.application
def test_apply_calendar_entities_and_taxonomy():
    svc, proj, basket, cand = _service_with_proposal()
    result = svc.apply_project_config_suggestion("b1")
    assert is_ok(result)
    applied = unwrap(result)
    assert applied["chronology"] is True
    assert applied["entities_placed"] == 1
    assert applied["taxonomy"] is True
    # Calendario aplicado al proyecto.
    meta = proj.project_chronology.metadata
    assert meta["mode"] == "vague_periods"
    assert "Antigua" in meta["eras"]
    # Entidad ubicada en el tiempo (en su candidato, sigue revisable).
    assert cand.proposed_data["birth_year"] == 900
    assert cand.proposed_data["death_year"] == 1180
    assert cand.proposed_data["temporal_nature"] == "mortal"
    # Taxonomía aplicada.
    assert "personaje" in proj.import_taxonomy.allowed_entity_types
    # Propuesta marcada como aplicada.
    assert basket.metadata["project_config_suggestion"]["applied"] is True


@pytest.mark.application
def test_nothing_applied_before_accept():
    _svc, proj, _basket, cand = _service_with_proposal()
    # Sin llamar a apply: canon/config intactos.
    assert cand.proposed_data.get("birth_year") is None
    assert proj.import_taxonomy.allowed_entity_types == []
    assert proj.entities == []


@pytest.mark.application
def test_apply_without_proposal_errors():
    proj = Project(name="I13")
    proj.import_baskets = [ImportBasket(id="b9", source_id="s", segments=[], import_candidates=[],
                                        review_state="pendiente", import_mode="canon", metadata={})]
    svc = ImportService(project_service=FakeProjectService(proj))
    assert is_error(svc.apply_project_config_suggestion("b9"))


@pytest.mark.application
def test_apply_never_creates_canon_entities():
    svc, proj, _basket, _cand = _service_with_proposal()
    svc.apply_project_config_suggestion("b1")
    # La ubicación temporal vive en el candidato, NO crea entidades de canon.
    assert proj.entities == []
