"""CRON — cableado IA del paso de recorrido cronológico.

Verifica que `chronology_walk_step` tiene prompt dedicado, tier CAUSAL, params
analíticos, y que `stage_results` convierte su payload en candidatos/diffs por
el MISMO pipeline que analyze_coherence (sin mutar canon).
"""

from __future__ import annotations

import pytest

from packages.application.ai_jobs import AIJob, AIJobType, stage_results
from packages.application.ai_request_gateway import INTENT_PARAMS
from packages.application.command_prompts import has_intent_prompt, system_prompt_for_intent
from packages.application.context_budget import INTENT_TO_TIER, ContextTier


@pytest.mark.application
def test_chronology_walk_step_has_dedicated_prompt():
    assert has_intent_prompt("chronology_walk_step")
    p = system_prompt_for_intent("chronology_walk_step")
    assert "RECORRIDO CRONOLÓGICO" in p
    assert "stop_required" in p
    assert "CONTEXTO ESTRATIFICADO" in p
    # No es el fallback genérico.
    assert "TERMINOLOGÍA DE DENDRO" not in p


@pytest.mark.application
def test_chronology_walk_step_tier_is_causal():
    assert INTENT_TO_TIER["chronology_walk_step"] is ContextTier.CAUSAL


@pytest.mark.application
def test_chronology_walk_step_params_are_analytical():
    params = INTENT_PARAMS["chronology_walk_step"]
    assert params.temperature <= 0.3  # analítico, frío por defecto
    assert params.max_tokens >= 2000


def _walk_scope(agresividad: str) -> dict:
    return {
        "selected_entity_ids": ["e1"],
        "directivas": {"parametros": {"agresividad": agresividad}},
    }


@pytest.mark.application
def test_stage_results_produces_milestone_and_edit_candidates():
    job = AIJob(
        type=AIJobType.CHRONOLOGY_WALK_STEP,
        prompt="Analiza el hito actual",
        # 'nuevas_piezas' permite hitos NUEVOS además de ediciones.
        context_scope=_walk_scope("sugerir_nuevas_piezas"),
    )
    payload = {
        "summary": "Punto de inflexión para Devian",
        "report": "Este hito funciona como punto de inflexión...",
        "diagnosis": "parcialmente_coherente",
        "issues": [
            {
                "title": "Servidumbre no motivada",
                "description": "Falta justificar la obediencia.",
                "severity": "alta",
                "kind": "motivation_incompatibility",
            }
        ],
        "hitos": [
            {
                "title": "Akshan perdona la vida a Devian",
                "summary": "Perdón en la Purga",
                "year": 100,
            }
        ],
        "entity_edits": [
            {"entity_name": "Devian", "field": "body", "proposed_value": "Sirve por deuda forzada."}
        ],
        "open_questions": ["¿Quién ordenó la Purga?"],
        "narrative_state": {"tension": "deuda vs persecución"},
        "stop_required": True,
        "stop_reason": "Motivación incompatible",
    }

    out = stage_results(payload, job)

    kinds = [c.get("proposed_data", {}).get("kind") for c in out["candidates"]]
    assert "causal_milestone" in kinds  # hito staged
    # PLAY-15: el formato escalar viejo se normaliza a un patch edit_fields.
    edit = next(
        c for c in out["candidates"]
        if (c.get("proposed_data") or {}).get("edit_kind") == "entity_edits"
    )
    assert edit["proposed_data"]["edit_fields"] == {
        "extended_description": "Sirve por deuda forzada."
    }
    # El payload crudo (con stop_required, issues, narrative_state) sobrevive intacto.
    assert out["model_payload"]["stop_required"] is True
    assert out["model_payload"]["issues"][0]["kind"] == "motivation_incompatibility"


@pytest.mark.application
def test_stage_results_edit_fields_respects_whitelist():
    """PLAY-15: patch multi-campo; visibilidad/canon se filtran en normalización."""
    job = AIJob(
        type=AIJobType.CHRONOLOGY_WALK_STEP,
        prompt="Edita",
        context_scope=_walk_scope("sugerir_reparaciones"),
    )
    payload = {
        "entity_edits": [
            {
                "entity_name": "Devian",
                "edit_fields": {
                    "name": "Devian el Roto",
                    "birth_year": -120,
                    "visibility_state": "oculto_al_jugador",
                    "canon_state": "canon",
                    "private_notes": "secreto",
                },
                "rationale": "coherencia",
            }
        ]
    }

    out = stage_results(payload, job)

    edit = next(
        c for c in out["candidates"]
        if (c.get("proposed_data") or {}).get("edit_kind") == "entity_edits"
    )
    # Los prohibidos (visibilidad/canon/secretos) JAMÁS llegan al candidato.
    assert edit["proposed_data"]["edit_fields"] == {
        "name": "Devian el Roto",
        "birth_year": -120,
    }


@pytest.mark.application
def test_stage_results_reparar_drops_new_milestone_keeps_edit():
    """REPARAR: el modelo NO puede crear un hito nuevo (evita el duplicado en otro
    año); solo se conservan las ediciones. La agresividad se enforza, no se confía
    al prompt."""
    job = AIJob(
        type=AIJobType.CHRONOLOGY_WALK_STEP,
        prompt="Repara el hito actual",
        context_scope=_walk_scope("sugerir_reparaciones"),
    )
    payload = {
        "report": "El hito marcador necesita contenido.",
        "hitos": [{"title": "Hito duplicado", "year": 86}],
        "milestone_edits": [
            {
                "target_id": "m1",
                "target_name": "nuevo hito",
                "field": "title",
                "proposed_value": "La Purga de Akshan",
            }
        ],
    }

    out = stage_results(payload, job)

    kinds = [c.get("proposed_data", {}).get("kind") for c in out["candidates"]]
    assert "causal_milestone" not in kinds  # NO se crea un hito nuevo en reparar
    edit = next(
        (c for c in out["candidates"] if c["proposed_data"].get("edit_kind") == "milestone_edits"),
        None,
    )
    assert edit is not None
    assert edit["proposed_data"]["edit_target_id"] == "m1"  # id estable ante renombrado


@pytest.mark.application
def test_stage_results_senalar_drops_all_structural():
    """solo_senalar: ni hitos ni ediciones; solo el informe revisable."""
    job = AIJob(
        type=AIJobType.CHRONOLOGY_WALK_STEP,
        prompt="Solo señala",
        context_scope=_walk_scope("solo_senalar"),
    )
    payload = {
        "report": "Señalo problemas sin tocar canon.",
        "hitos": [{"title": "x", "year": 10}],
        "milestone_edits": [
            {"target_id": "m1", "target_name": "y", "field": "title", "proposed_value": "z"}
        ],
    }

    out = stage_results(payload, job)

    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["candidate_type"] == "sugerencia_ia"
    assert not out["candidates"][0]["proposed_data"].get("edit_proposed_value")


@pytest.mark.application
def test_stage_results_emits_report_candidate_when_no_structural_changes():
    job = AIJob(
        type=AIJobType.CHRONOLOGY_WALK_STEP,
        prompt="Solo señalar",
        context_scope={"selected_entity_ids": ["e1"]},
    )
    payload = {
        "summary": "Lectura sin reparaciones",
        "report": "El hito encaja, pero hay una oportunidad menor.",
        "issues": [
            {"title": "Oportunidad", "description": "x", "severity": "baja", "kind": "opportunity"}
        ],
        "stop_required": False,
    }

    out = stage_results(payload, job)

    # Modo 'solo señalar': sin estructurales → un candidato-informe revisable.
    assert len(out["candidates"]) == 1
    report_candidate = out["candidates"][0]
    assert report_candidate["candidate_type"] == "sugerencia_ia"
    assert report_candidate["proposed_data"]["issues"][0]["kind"] == "opportunity"
