"""PA01: ensamblado del prompt con secciones por autoridad y presupuesto por tier."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from packages.application.prompt_assembler import (
    PromptAssembler,
    build_model_user_message,
)


def _plan(prompt="haz algo", context=None, intent="suggest_relations"):
    """Plan duck-typed: el assembler solo lee prompt/context/intent.intent_type.value."""
    return SimpleNamespace(
        prompt=prompt,
        context=context or {},
        intent=SimpleNamespace(intent_type=SimpleNamespace(value=intent)),
    )


def _pack(items, *, warnings=None):
    return {
        "schema": "context_pack/v1",
        "items": items,
        "warnings": warnings or [],
        "tokens_budget": 2400,
        "tokens_estimated": 10,
        "truncated": False,
    }


def _msg(plan):
    return json.loads(PromptAssembler().assemble(plan))


def test_assemble_returns_cone_sections():
    msg = _msg(_plan(context={
        "creative_brief": {"canon": {"hard_rules": ["r"]}, "primary_language": "es"},
        "selected_entity_ids": ["e1"],
    }))
    assert "prompt_exacto_usuario" in msg
    # PA03: config creativa completa en una sola sección; sin cerco_canon/parametros.
    assert "configuracion_creativa" in msg
    assert "cerco_canon" not in msg
    assert "parametros_permanentes" not in msg
    assert "seleccion" in msg


def test_user_prompt_is_sacred():
    long_prompt = "palabra " * 5000
    msg = _msg(_plan(prompt=long_prompt, context={"prompt_budget_tokens": 1000}))
    assert msg["prompt_exacto_usuario"] == long_prompt


def test_rag_pack_partitioned_by_authority():
    pack = _pack(
        [
            {
                "kind": "entity",
                "ref_id": "e1",
                "rendered_text": "Ariadna",
                "priority": "required",
                "reason": "sel",
            },
            {
                "kind": "relation",
                "ref_id": "r1",
                "rendered_text": "e1→e2",
                "priority": "high",
                "reason": "rel",
            },
            {
                "kind": "candidate",
                "ref_id": "c1",
                "rendered_text": "propuesta",
                "priority": "normal",
                "reason": "pend",
            },
            {
                "kind": "import_document",
                "ref_id": "d1",
                "rendered_text": "doc",
                "priority": "low",
                "reason": "imp",
            },
            {
                "kind": "issue",
                "ref_id": "i1",
                "rendered_text": "issue",
                "priority": "normal",
                "reason": "iss",
            },
        ]
    )
    msg = _msg(_plan(context={"rag_context_pack": pack}))

    # Canon confirmado: entity + relation.
    canon_ids = {it["ref_id"] for it in msg["canon_confirmado"]["items"]}
    assert canon_ids == {"e1", "r1"}
    assert "CANON CONFIRMADO" in msg["canon_confirmado"]["autoridad"]

    # Candidates pendientes: claramente NO canon.
    assert {it["ref_id"] for it in msg["candidates_pendientes"]["items"]} == {"c1"}
    assert "NO" in msg["candidates_pendientes"]["autoridad"].upper()

    # Imports sin revisar: fuente externa.
    assert {it["ref_id"] for it in msg["importaciones_sin_revisar"]["items"]} == {"d1"}

    # RAG auxiliar: lo demás (issue/creative_config).
    assert {it["ref_id"] for it in msg["rag_auxiliar"]["items"]} == {"i1"}


def test_rag_pack_removed_from_authorized_context():
    pack = _pack(
        [
            {
                "kind": "entity",
                "ref_id": "e1",
                "rendered_text": "x",
                "priority": "high",
                "reason": "r",
            }
        ]
    )
    msg = _msg(_plan(context={"rag_context_pack": pack, "algo_libre": "se queda"}))
    # El pack ya no se duplica en contexto_autorizado.
    assert "rag_context_pack" not in json.dumps(msg.get("contexto_autorizado", {}))
    # El contexto libre sí permanece como residual.
    assert msg["contexto_autorizado"]["algo_libre"] == "se queda"


def test_rag_warnings_surface_in_rag_auxiliar():
    pack = _pack([], warnings=["rag_project_unavailable"])
    msg = _msg(_plan(context={"rag_context_pack": pack}))
    assert msg["rag_auxiliar"]["warnings"] == ["rag_project_unavailable"]
    assert "canon_confirmado" not in msg


def test_empty_pack_emits_no_authority_sections():
    msg = _msg(_plan(context={"rag_context_pack": _pack([])}))
    for key in (
        "canon_confirmado",
        "candidates_pendientes",
        "importaciones_sin_revisar",
        "rag_auxiliar",
    ):
        assert key not in msg


def test_budget_override_shrinks_flexible_content():
    # PA03: la config creativa es fija; el presupuesto recorta lo FLEXIBLE (canon
    # recuperado). Más presupuesto ⇒ caben más items.
    pack = _pack([
        {"kind": "entity", "ref_id": f"e{i}", "rendered_text": "palabra " * 60,
         "priority": "normal", "reason": "text_overlap"}
        for i in range(30)
    ])
    small = _msg(_plan(context={"rag_context_pack": pack, "prompt_budget_tokens": 1000}))
    large = _msg(_plan(context={"rag_context_pack": pack, "prompt_budget_tokens": 20000}))
    assert len(json.dumps(small)) < len(json.dumps(large))


def test_configuracion_creativa_complete_and_pruned():
    brief = {
        "primary_language": "es",
        "genre": {
            "primary_genre": "Histórico",
            "secondary_genres": [],
            "subgenres": ["Folk Horror"],
        },
        "tone": {"narrative_tone": "Sombrío", "dark_level": "", "formality_level": ""},
        "realism": {"realism_level": "medium", "fantasy_level": "", "science_level": ""},
        "taste_memory": {"likes": ["tragedia"]},
        "canon": {"hard_rules": ["La caída es inevitable"], "continuity_strictness": 9},
        "negative_space": {},
    }
    msg = _msg(_plan(context={"creative_brief": brief}))
    cfg = msg["configuracion_creativa"]
    # Completa: taste_memory viaja (antes se descartaba).
    assert cfg["taste_memory"] == {"likes": ["tragedia"]}
    assert cfg["canon"]["hard_rules"] == ["La caída es inevitable"]
    # Sin ruido: campos vacíos podados.
    assert "dark_level" not in cfg["tone"]
    assert "fantasy_level" not in cfg["realism"]
    assert "secondary_genres" not in cfg["genre"]
    assert "negative_space" not in cfg


def test_chronology_formats_only_for_milestones():
    with_fmt = _msg(_plan(intent="propose_milestones"))
    assert "formatos_h05" in with_fmt
    # Nota: el intent value se incluye en la heurística de hints, así que se usa
    # uno sin subcadenas de hint ("era" vive dentro de "generate", p.ej.).
    without = _msg(_plan(prompt="describe la facción", intent="edit_relation"))
    assert "formatos_h05" not in without


def test_debug_log_emitted_at_debug_level(caplog):
    with caplog.at_level(logging.DEBUG, logger="narrative.prompt_assembler"):
        _msg(_plan(intent="suggest_relations"))
    assert any("PROMPT_DEBUG" in r.message for r in caplog.records)
    record = next(r for r in caplog.records if "PROMPT_DEBUG" in r.message)
    text = record.getMessage()
    assert "tier=causal" in text
    assert "input_budget=40000" in text


def test_shim_delegates_to_assembler():
    plan = _plan()
    assert build_model_user_message(plan) == PromptAssembler().assemble(plan)
