"""UX3: AIJobService.preview_context calcula el contexto SIN crear ni ejecutar job."""

from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import SimulatedAIProvider


def _service():
    # Sin rag_service: _with_rag_context deja el contexto intacto (lo que pasemos
    # en context_scope viaja tal cual al ensamblado). Suficiente para la preview.
    return AIJobService(provider=SimulatedAIProvider())


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


def test_preview_context_surfaces_contexto_wiki_as_fixed():
    # BETA2-WIKI-05: el contexto lo aporta la navegación de la wiki (contexto_wiki),
    # que viaja como sección fija (ya viene acotada por el WikiNavigator).
    service = _service()
    result = service.preview_context(
        AIJobType.SUGGEST_RELATIONS,
        "relaciona",
        context_scope={
            "contexto_wiki": {
                "nota": "x",
                "paginas": [{"kind": "entity", "id": "e1", "resumen": "Ariadna"}],
                "canon": [],
            }
        },
    )
    wiki = next(s for s in result.value["sections"] if s["key"] == "contexto_wiki")
    assert wiki["fixed"] is True


def test_preview_context_respects_section_exclusions():
    # La exclusión a nivel de sección sigue vigente (la de por-ítem del RAG se retiró).
    service = _service()
    result = service.preview_context(
        AIJobType.SUGGEST_RELATIONS,
        "relaciona",
        context_scope={
            "vecindario": {"items": [{"id": "v1", "rendered_text": "vecino"}]},
            "preview_exclusions": {"sections": ["vecindario"], "item_ids": []},
        },
    )
    keys = {s["key"] for s in result.value["sections"]}
    assert "vecindario" not in keys
