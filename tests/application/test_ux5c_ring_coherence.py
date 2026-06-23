"""BETA1-UX5c — coherencia con el anillo activo al crear/editar entidades.

El anillo activo debe viajar al modelo con su DESCRIPCIÓN y DOMINIO (no solo el id/
nombre), para que una entidad creada en un anillo cosmológico sea cosmológica, no
mundana. Deterministas (sin modelo).
"""
from __future__ import annotations

from types import SimpleNamespace

from packages.application.ai_jobs import _active_ring_brief
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.prompt_assembler import _selection_block


def _project_with_ring(ring_id="ring-cosmos", name="Designio Oculto",
                       description="Anillo de entidades cosmológicas y fuerzas del destino.",
                       domain="cosmologia"):
    layer = SimpleNamespace(
        id=ring_id, name=name, description=description, metadata={"domain": domain},
    )
    return SimpleNamespace(world_layers=[layer])


# ── _active_ring_brief ────────────────────────────────────────────────────


def test_active_ring_brief_returns_name_description_domain():
    proj = _project_with_ring()
    brief = _active_ring_brief(proj, {"active_ring_id": "ring-cosmos"})
    assert brief["name"] == "Designio Oculto"
    assert "cosmológicas" in brief["description"]
    assert brief["domain"] == "cosmologia"


def test_active_ring_brief_uses_focused_ring_id_fallback():
    proj = _project_with_ring()
    brief = _active_ring_brief(proj, {"focused_ring_id": "ring-cosmos"})
    assert brief["id"] == "ring-cosmos"


def test_active_ring_brief_empty_without_ring_or_match():
    proj = _project_with_ring()
    assert _active_ring_brief(proj, {}) == {}
    assert _active_ring_brief(proj, {"active_ring_id": "inexistente"}) == {}
    assert _active_ring_brief(None, {"active_ring_id": "ring-cosmos"}) == {}


# ── _selection_block surfacea la semántica del anillo ─────────────────────


def test_selection_block_surfaces_active_ring_semantics():
    block = _selection_block({
        "active_ring_id": "ring-cosmos",
        "focus_label": "Anillo: Designio Oculto",
        "active_ring": {
            "id": "ring-cosmos", "name": "Designio Oculto",
            "description": "Anillo de entidades cosmológicas.", "domain": "cosmologia",
        },
    })
    assert block["anillo_activo_nombre"] == "Designio Oculto"
    assert block["anillo_activo_descripcion"] == "Anillo de entidades cosmológicas."
    assert block["anillo_activo_dominio"] == "cosmologia"
    assert "coherencia_anillo" in block
    assert "cosmológic" in block["coherencia_anillo"]


def test_selection_block_omits_ring_semantics_when_absent():
    block = _selection_block({"selected_entity_ids": ["e1"]})
    assert "anillo_activo_descripcion" not in block
    assert "coherencia_anillo" not in block


# ── el prompt instruye coherencia con el anillo ───────────────────────────


def test_generate_entities_prompt_instructs_ring_coherence():
    prompt = system_prompt_for_intent("generate_entities")
    assert "ANILLO ACTIVO" in prompt
    assert "anillo_activo_descripcion" in prompt


def test_generate_tree_prompt_instructs_ring_coherence():
    prompt = system_prompt_for_intent("generate_tree")
    assert "ANILLO ACTIVO" in prompt
