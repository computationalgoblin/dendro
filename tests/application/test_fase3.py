"""Fase 3: causal context ordering + model-param overrides (radial tuners)."""
from __future__ import annotations

import json

from packages.application.ai_jobs import (
    AIJobService,
    AIJobType,
    CommandBarIntent,
    build_job_plan,
    build_model_user_message,
)
from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest, ModelParams
from packages.application.command_expansion import order_context_by_causality
from packages.domain.result import Ok

# --- F3.1 causal ordering --------------------------------------------------

def _ctx():
    return dict(
        rings=[
            {"id": "r2", "name": "Vida", "order": 2},
            {"id": "r1", "name": "Materia", "order": 1},
        ],
        entities=[
            {"id": "rama1", "name": "Orden", "display_type": "rama"},
            {"id": "h1", "name": "Ariadna", "display_type": "hoja"},
            {"id": "h2", "name": "Namar", "entity_type": "personaje"},
        ],
        relations=[
            {"id": "rel_bb", "source_id": "rama1", "target_id": "rama1"},
            {"id": "rel_ll", "source_id": "h1", "target_id": "h2"},
            {"id": "rel_mix", "source_id": "rama1", "target_id": "h1"},
        ],
        milestones=[
            {"id": "m1", "title": "Origen", "layer_ids": ["r1"]},
            {"id": "m_free", "title": "Suelto", "layer_ids": []},
        ],
    )


def test_rings_sorted_by_order_with_their_milestones():
    out = order_context_by_causality(**_ctx())
    assert [a["id"] for a in out["anillos"]] == ["r1", "r2"]  # order 1 before 2
    assert [m["id"] for m in out["anillos"][0]["hitos"]] == ["m1"]
    assert out["orden"] == ["anillos", "ramas", "hojas"]
    assert "causalidad" in out["instruccion"].lower()


def test_branches_and_leaves_split():
    out = order_context_by_causality(**_ctx())
    assert [e["id"] for e in out["ramas"]] == ["rama1"]
    assert {e["id"] for e in out["hojas"]} == {"h1", "h2"}  # hoja + personaje


def test_relations_split_by_level():
    out = order_context_by_causality(**_ctx())
    assert [r["id"] for r in out["relaciones_entre_ramas"]] == ["rel_bb"]
    assert [r["id"] for r in out["relaciones_entre_hojas"]] == ["rel_ll"]
    assert [r["id"] for r in out["relaciones_mixtas"]] == ["rel_mix"]


def test_unbound_milestones_reported():
    out = order_context_by_causality(**_ctx())
    assert [m["id"] for m in out["hitos_sin_anillo"]] == ["m_free"]


def test_empty_context_is_safe():
    out = order_context_by_causality()
    assert out["anillos"] == [] and out["ramas"] == [] and out["hojas"] == []


# --- F3.2 inclusion in the model message -----------------------------------

def test_model_message_includes_seeded_causal_context():
    intent = CommandBarIntent(AIJobType.GENERATE_ENTITIES, 1.0, "selection", "entity_candidates")
    causal = order_context_by_causality(**_ctx())
    plan = build_job_plan(intent, "crea algo", {"contexto_causal": causal})
    msg = json.loads(build_model_user_message(plan))
    assert msg["contexto_causal"]["orden"] == ["anillos", "ramas", "hojas"]


# --- F3.3 model-param overrides (radial tuners) ----------------------------

class RecordingProvider:
    provider_name = "rec"
    model = "rec-model"

    def __init__(self):
        self.last_temperature = None
        self.last_max_tokens = None

    def chat(self, system_prompt, user_message, timeout=None, *,
             temperature=None, max_tokens=None, json_mode=False):
        self.last_temperature = temperature
        self.last_max_tokens = max_tokens
        return "{}", None


def test_gateway_uses_intent_defaults_without_override():
    provider = RecordingProvider()
    AIRequestGateway(provider=provider).execute(
        GatewayRequest(intent="generate_entities", user_prompt="x")
    )
    expected = ModelParams.from_intent("generate_entities")
    assert provider.last_temperature == expected.temperature
    assert provider.last_max_tokens == expected.max_tokens


def test_gateway_applies_request_overrides():
    provider = RecordingProvider()
    AIRequestGateway(provider=provider).execute(
        GatewayRequest(intent="generate_entities", user_prompt="x", temperature=0.1, max_tokens=64)
    )
    assert provider.last_temperature == 0.1
    assert provider.last_max_tokens == 64


def test_execute_job_passes_tuner_overrides_end_to_end():
    provider = RecordingProvider()
    service = AIJobService(provider=provider)
    result = service.run_focused_job(
        AIJobType.GENERATE_ENTITIES,
        "crea una hoja",
        context_scope={"model_temperature": 0.15, "model_max_tokens": 128},
    )
    assert isinstance(result, Ok)
    assert provider.last_temperature == 0.15
    assert provider.last_max_tokens == 128


# --- F3.4 radial tuner drag→value math (pure, no QApplication) -------------

def test_radial_tuner_math():
    from hosts.DesktopHostPySide.widgets.radial_tuner import (
        clamp01,
        drag_to_fraction,
        fraction_from_value,
        value_from_fraction,
    )
    # Dragging up fills; dragging down empties; clamped to [0,1].
    assert drag_to_fraction(0.5, 20, 40) == 1.0      # +half span → clamps at full
    assert drag_to_fraction(0.5, -20, 40) == 0.0     # -half span → empty
    assert abs(drag_to_fraction(0.0, 10, 40) - 0.25) < 1e-9
    assert clamp01(2.0) == 1.0 and clamp01(-1.0) == 0.0
    # value <-> fraction round-trip.
    assert fraction_from_value(0.5, 0.0, 1.0) == 0.5
    assert value_from_fraction(0.5, 0.0, 2.0) == 1.0
    assert fraction_from_value(2000, 1000, 3000) == 0.5
