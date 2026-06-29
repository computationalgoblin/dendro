"""I13 — aplicar la propuesta de config de proyecto (acción explícita).

Aceptar aplica el calendario (apply_candidate), ubica las entidades en el tiempo
(mergea birth/death/nature en sus candidatos) y aplica tono/género a
``creative_config``. Antes de aceptar no se aplica nada. Nunca escribe canon
directamente.

PA04: la taxonomía de importación se eliminó (``project.import_taxonomy`` ya no
existe); tono/género ahora se aplican a ``creative_config`` (estilo.tono /
identidad.genero_principal), solo si están vacíos. Las aserciones de taxonomía se
retiraron.
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
        "world_layers": {
            "activate_default_layer_ids": ["layer_historia"],
            "custom_layers": [
                {"name": "Linaje real", "description": "Sucesión dinástica",
                 "causal_role": "dynasty", "causal_parent_layer_ids": ["layer_historia"]},
            ],
        },
        "milestones": [
            {"title": "Caída del reino", "description": "El fin de la dinastía.",
             "milestone_type": "caida", "year": 1180, "date_label": "",
             "affected_layer_ids": ["layer_historia", "Linaje real"], "tags": [], "rationale": ""},
        ],
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
def test_apply_calendar_entities_and_tone_genre():
    svc, proj, basket, cand = _service_with_proposal()
    result = svc.apply_project_config_suggestion("b1")
    assert is_ok(result)
    applied = unwrap(result)
    assert applied["chronology"] is True
    assert applied["entities_placed"] == 1
    assert applied["tone_genre"] is True
    # PA04: tono/género aplicados a creative_config (sin pisar lo del usuario).
    assert proj.creative_config.estilo.tono == "épico"
    assert proj.creative_config.identidad.genero_principal == "fantasía"
    # Calendario aplicado al proyecto.
    meta = proj.project_chronology.metadata
    assert meta["mode"] == "vague_periods"
    assert "Antigua" in meta["eras"]
    # Entidad ubicada en el tiempo (en su candidato, sigue revisable).
    assert cand.proposed_data["birth_year"] == 900
    assert cand.proposed_data["death_year"] == 1180
    assert cand.proposed_data["temporal_nature"] == "mortal"
    # Andamiaje: anillos (1 predefinido activado + 1 a medida creado).
    assert applied["world_layers_activated"] == 1
    assert applied["world_layers_created"] == 1
    hist = [wl for wl in proj.world_layers if wl.id == "layer_historia"]
    assert len(hist) == 1 and hist[0].is_default is True
    custom = [wl for wl in proj.world_layers if wl.name == "Linaje real"]
    assert len(custom) == 1
    assert custom[0].metadata.get("causal_role") == "dynasty"
    assert "layer_historia" in custom[0].metadata.get("causal_parent_layer_ids", "")
    # Andamiaje: hito datado en canon y enlazado a la cronología.
    assert applied["milestones"] == 1
    assert len(proj.causal_milestones) == 1
    hito = proj.causal_milestones[0]
    assert hito.year == 1180
    assert hito.id in proj.project_chronology.milestone_ids
    # affected_layer_ids resueltos: id del catálogo + custom por nombre → id real.
    assert "layer_historia" in hito.affected_layer_ids
    assert custom[0].id in hito.affected_layer_ids
    # Propuesta marcada como aplicada.
    assert basket.metadata["project_config_suggestion"]["applied"] is True


@pytest.mark.application
def test_reapply_is_blocked():
    svc, _proj, _basket, _cand = _service_with_proposal()
    assert is_ok(svc.apply_project_config_suggestion("b1"))
    # Re-aplicar la misma propuesta debe fallar (guarda de idempotencia).
    assert is_error(svc.apply_project_config_suggestion("b1"))


@pytest.mark.application
def test_default_layer_not_duplicated_if_already_present():
    from packages.domain.world_layer import default_world_layers

    svc, proj, _basket, _cand = _service_with_proposal()
    # El proyecto YA tiene la capa de historia: activar no debe duplicarla.
    proj.world_layers.append(next(wl for wl in default_world_layers() if wl.id == "layer_historia"))
    result = svc.apply_project_config_suggestion("b1")
    assert is_ok(result)
    assert unwrap(result)["world_layers_activated"] == 0
    assert len([wl for wl in proj.world_layers if wl.id == "layer_historia"]) == 1


@pytest.mark.application
def test_nothing_applied_before_accept():
    _svc, proj, _basket, cand = _service_with_proposal()
    # Sin llamar a apply: canon/config intactos.
    assert cand.proposed_data.get("birth_year") is None
    # PA04: tono/género viven en creative_config y siguen vacíos antes de aceptar.
    assert proj.creative_config.estilo.tono == ""
    assert proj.creative_config.identidad.genero_principal == ""
    assert proj.entities == []


@pytest.mark.application
def test_apply_tone_genre_does_not_overwrite_user_choices():
    svc, proj, _basket, _cand = _service_with_proposal()
    # PA04: el usuario ya fijó tono/género en creative_config: NO debe pisarlos.
    proj.creative_config.estilo.tono = "sombrío"
    proj.creative_config.identidad.genero_principal = "terror"
    svc.apply_project_config_suggestion("b1")
    assert proj.creative_config.estilo.tono == "sombrío"
    assert proj.creative_config.identidad.genero_principal == "terror"


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
