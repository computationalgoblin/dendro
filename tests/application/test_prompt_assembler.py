"""PA01: ensamblado del prompt con secciones por autoridad y presupuesto por tier."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from packages.application.prompt_assembler import (
    PromptAssembler,
    apply_section_exclusions,
    build_context_preview,
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


def test_rag_pack_no_longer_partitioned():
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
                "kind": "issue",
                "ref_id": "i1",
                "rendered_text": "issue",
                "priority": "normal",
                "reason": "iss",
            },
        ]
    )
    msg = _msg(_plan(context={"rag_context_pack": pack}))
    # BETA2-WIKI-05: el pack RAG ya NO se particiona en secciones de autoridad;
    # el contexto relevante lo aporta la navegación de la wiki (contexto_wiki).
    for retired in ("canon_confirmado", "candidates_pendientes", "rag_auxiliar"):
        assert retired not in msg


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


def test_rag_warnings_no_longer_surface():
    # BETA2-WIKI-05: el pack RAG está retirado del ensamblado; sus warnings no viajan.
    pack = _pack([], warnings=["rag_project_unavailable"])
    msg = _msg(_plan(context={"rag_context_pack": pack}))
    assert "rag_auxiliar" not in msg


def test_empty_pack_emits_no_authority_sections():
    msg = _msg(_plan(context={"rag_context_pack": _pack([])}))
    for key in (
        "canon_confirmado",
        "candidates_pendientes",
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


# ── UX3: vista previa de contexto + exclusiones ──────────────────────────


def test_preview_trimmed_matches_assemble():
    # preview()['trimmed'] es exactamente lo que assemble() serializa.
    plan = _plan(context={
        "creative_brief": {"canon": {"hard_rules": ["r"]}},
        "rag_context_pack": _pack([
            {"kind": "entity", "ref_id": "e1", "rendered_text": "x",
             "priority": "high", "reason": "r"},
        ]),
    })
    asm = PromptAssembler()
    assert json.loads(asm.assemble(plan)) == asm.preview(plan)["trimmed"]


def test_apply_section_exclusions_drops_rag_item_by_id():
    pack = _pack([
        {"kind": "entity", "ref_id": "e1", "rendered_text": "x", "priority": "high", "reason": "r"},
        {"kind": "entity", "ref_id": "e2", "rendered_text": "y", "priority": "high", "reason": "r"},
    ])
    ctx = apply_section_exclusions({"rag_context_pack": pack}, [], ["e1"])
    ids = {it["ref_id"] for it in ctx["rag_context_pack"]["items"]}
    assert ids == {"e2"}


def test_apply_section_exclusions_drops_whole_rag_section():
    pack = _pack([
        {"kind": "entity", "ref_id": "e1", "rendered_text": "x",
         "priority": "high", "reason": "r"},
        {"kind": "candidate", "ref_id": "c1", "rendered_text": "p",
         "priority": "normal", "reason": "r"},
    ])
    ctx = apply_section_exclusions({"rag_context_pack": pack}, ["canon_confirmado"], [])
    kinds = {it["kind"] for it in ctx["rag_context_pack"]["items"]}
    assert kinds == {"candidate"}  # canon eliminado, candidato conservado


def test_apply_section_exclusions_drops_deterministic_section():
    ctx = apply_section_exclusions(
        {"cronologia": {"nombre": "Calendario"}, "contexto_causal": {"a": 1}},
        ["cronologia"],
        [],
    )
    assert "cronologia" not in ctx
    assert "contexto_causal" in ctx  # solo se quita lo excluido


def test_apply_section_exclusions_ignores_fixed_sections():
    # Las secciones fijas/sagradas no son excluibles: no se tocan aunque lleguen.
    ctx = apply_section_exclusions(
        {"creative_brief": {"canon": {}}, "rag_context_pack": _pack([])},
        ["configuracion_creativa", "prompt_exacto_usuario"],
        [],
    )
    assert ctx["creative_brief"] == {"canon": {}}


def test_section_exclusion_drops_flexible_section():
    # BETA2-WIKI-05: la exclusión por-ítem del pack RAG queda retirada. La exclusión
    # a nivel de SECCIÓN sigue: excluir una sección flexible la quita del mensaje real.
    plan = _plan(context={
        "vecindario": {"items": [{"id": "v1", "rendered_text": "vecino"}]},
        "preview_exclusions": {"sections": ["vecindario"], "item_ids": []},
    })
    msg = json.loads(PromptAssembler().assemble(plan))
    assert "vecindario" not in msg


def test_build_context_preview_structure():
    # BETA2-WIKI-05: sin pack RAG. La vista previa distingue secciones fijas (sagradas)
    # de flexibles (excluibles). contexto_wiki es fija; vecindario es flexible.
    plan = _plan(context={
        "creative_brief": {"canon": {"hard_rules": ["r"]}},
        "contexto_wiki": {"nota": "x", "paginas": [{"kind": "entity", "id": "e1"}], "canon": []},
        "vecindario": {"items": [{"id": "v1", "rendered_text": "vecino"}]},
    })
    preview = build_context_preview(PromptAssembler().preview(plan))
    by_key = {s["key"]: s for s in preview["sections"]}
    # Sección sagrada y contexto_wiki: fijas, NO excluibles.
    assert by_key["prompt_exacto_usuario"]["fixed"] is True
    assert by_key["contexto_wiki"]["fixed"] is True
    # Sección flexible: excluible.
    assert by_key["vecindario"]["fixed"] is False
    assert preview["total_tokens"] >= 1
