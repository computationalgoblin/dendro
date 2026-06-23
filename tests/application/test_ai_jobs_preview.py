"""UX3: AIJobService.preview_context calcula el contexto SIN crear ni ejecutar job."""

from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import SimulatedAIProvider


def _service():
    # Sin rag_service: _with_rag_context deja el contexto intacto (lo que pasemos
    # en context_scope viaja tal cual al ensamblado). Suficiente para la preview.
    return AIJobService(provider=SimulatedAIProvider())


def _pack(items):
    return {"schema": "context_pack/v1", "items": items, "warnings": [], "truncated": False}


def test_preview_context_does_not_create_a_job():
    service = _service()
    result = service.preview_context(
        AIJobType.GENERATE_ENTITIES, "un herrero exiliado", context_scope={}
    )
    assert isinstance(result, Ok)
    assert service.list_jobs() == []  # efímero: no se registra


def test_preview_context_empty_prompt_errors():
    result = _service().preview_context(AIJobType.GENERATE_ENTITIES, "   ")
    assert isinstance(result, Error)


def test_preview_context_returns_sections_with_user_prompt():
    service = _service()
    result = service.preview_context(
        AIJobType.GENERATE_ENTITIES,
        "una orden de monjes",
        context_scope={"creative_brief": {"canon": {"hard_rules": ["la caída es inevitable"]}}},
    )
    preview = result.value
    keys = {s["key"] for s in preview["sections"]}
    assert "prompt_exacto_usuario" in keys
    assert "configuracion_creativa" in keys
    assert preview["input_budget"] >= 1
    assert preview["tier"]


def test_preview_context_surfaces_rag_items_as_excludable():
    service = _service()
    pack = _pack([
        {"kind": "entity", "ref_id": "e1", "rendered_text": "Ariadna",
         "priority": "high", "reason": "sel"},
    ])
    result = service.preview_context(
        AIJobType.SUGGEST_RELATIONS, "relaciona", context_scope={"rag_context_pack": pack}
    )
    preview = result.value
    canon = next(s for s in preview["sections"] if s["key"] == "canon_confirmado")
    assert canon["fixed"] is False  # excluible por el usuario
    assert canon["items"][0]["ref_id"] == "e1"


def test_preview_context_respects_exclusions():
    service = _service()
    pack = _pack([
        {"kind": "entity", "ref_id": "keep", "rendered_text": "x",
         "priority": "high", "reason": "r"},
        {"kind": "entity", "ref_id": "drop", "rendered_text": "y",
         "priority": "high", "reason": "r"},
    ])
    result = service.preview_context(
        AIJobType.SUGGEST_RELATIONS,
        "relaciona",
        context_scope={
            "rag_context_pack": pack,
            "preview_exclusions": {"sections": [], "item_ids": ["drop"]},
        },
    )
    canon = next(s for s in result.value["sections"] if s["key"] == "canon_confirmado")
    assert {it["ref_id"] for it in canon["items"]} == {"keep"}
