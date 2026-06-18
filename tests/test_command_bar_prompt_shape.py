"""Tests para la forma del mensaje de la command bar (cono de autoridad + M2/M4/M7).

Verifica build_model_user_message: secciones del cono, sin duplicados, menciones
con mini-ficha, vecindario condicional y respeto del presupuesto.
"""

import json

from packages.application.ai_jobs import (
    AIJobService,
    AIJobType,
    CommandBarIntent,
    build_job_plan,
    build_model_user_message,
)
from packages.infrastructure.ai_provider import SimulatedAIProvider


def _plan(prompt="crea algo", context=None):
    intent = CommandBarIntent(AIJobType.GENERATE_ENTITIES, 1.0, "selection", "entity_candidates")
    return build_job_plan(intent, prompt, context or {})


def test_message_drops_intent_and_plan():
    msg = json.loads(build_model_user_message(_plan()))
    assert "intent" not in msg
    assert "plan" not in msg


def test_message_has_cone_sections():
    msg = json.loads(build_model_user_message(_plan(context={
        "creative_brief": {"canon": {"hard_rules": ["regla"]}, "primary_language": "es"},
        "selected_entity_ids": ["e1"],
    })))
    # PA03: la config creativa viaja completa en una única sección determinista.
    assert "configuracion_creativa" in msg
    assert "cerco_canon" not in msg
    assert "parametros_permanentes" not in msg
    assert "seleccion" in msg


def test_message_no_legacy_profile():
    msg = json.loads(build_model_user_message(_plan()))
    assert "perfil_creativo_b40" not in msg


def test_authorized_context_dedup():
    context = {
        "creative_brief": {"canon": {"hard_rules": ["regla"]}},
        "contexto_causal": {"orden": ["anillos", "ramas", "hojas"]},
        "vecindario": {"items": [{"entity_id": "B", "hop": 1}]},
        "creative_context": [{"name": "x"}],
        "branch_creative_context": [{"name": "y"}],
        "algo_libre": "se queda",
    }
    msg = json.loads(build_model_user_message(_plan(context=context)))
    auth = msg["contexto_autorizado"]
    assert "creative_brief" not in auth
    assert "contexto_causal" not in auth
    assert "vecindario" not in auth
    assert "creative_context" not in auth
    assert "branch_creative_context" not in auth
    assert auth.get("algo_libre") == "se queda"


def test_mentions_with_brief():
    context = {
        "mentions": {"refs": [{
            "name": "Ariadna", "ref_type": "entity",
            "brief": {"type": "personaje", "layer_ids": ["L1"], "brief_description": "exploradora"},
        }]},
    }
    msg = json.loads(build_model_user_message(_plan(context=context)))
    men = msg["menciones"][0]
    assert men["name"] == "Ariadna"
    assert men["type"] == "personaje"
    assert men["layer_ids"] == ["L1"]
    assert men["brief_description"] == "exploradora"


def test_mentions_without_brief():
    context = {"mentions": {"refs": [{"name": "Namar", "ref_type": "entity"}]}}
    msg = json.loads(build_model_user_message(_plan(context=context)))
    men = msg["menciones"][0]
    assert men == {"name": "Namar", "ref_type": "entity"}


def test_vecindario_present_only_with_items():
    with_items = json.loads(build_model_user_message(_plan(context={
        "vecindario": {"items": [{"entity_id": "B", "hop": 1}]},
    })))
    assert "vecindario" in with_items
    empty = json.loads(build_model_user_message(_plan(context={"vecindario": {"items": []}})))
    assert "vecindario" not in empty


def test_budget_shrinks_message():
    # PA03: la config creativa es FIJA (siempre completa); lo que el presupuesto
    # reparte/recorta es el contenido FLEXIBLE (p. ej. canon recuperado por RAG).
    pack = {
        "schema": "context_pack/v1",
        "items": [
            {"kind": "entity", "ref_id": f"e{i}", "rendered_text": "palabra " * 60,
             "priority": "normal", "reason": "text_overlap"}
            for i in range(30)
        ],
        "warnings": [],
        "tokens_budget": 2400,
        "tokens_estimated": 100,
        "truncated": False,
    }
    small = json.loads(build_model_user_message(_plan(context={
        "rag_context_pack": pack, "prompt_budget_tokens": 1000,
    })))
    large = json.loads(build_model_user_message(_plan(context={
        "rag_context_pack": pack, "prompt_budget_tokens": 20000,
    })))
    assert len(json.dumps(small)) < len(json.dumps(large))


def test_user_prompt_never_truncated():
    long_prompt = "palabra " * 5000
    msg = json.loads(build_model_user_message(_plan(prompt=long_prompt, context={
        "prompt_budget_tokens": 1000,
    })))
    assert msg["prompt_exacto_usuario"] == long_prompt.strip()


def test_smoke_simulated_provider_executes():
    service = AIJobService(provider=SimulatedAIProvider(), allow_simulated=True)
    result = service.create_job(
        AIJobType.GENERATE_ENTITIES,
        "Créame tres personajes",
        context_scope={"selected_entity_ids": ["e1"]},
        explicit=True,
    )
    job = result.value
    exec_result = service.execute_job(job.id)
    # No falla y produce estructura.
    assert exec_result.value.result is not None
