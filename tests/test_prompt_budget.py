"""Tests para packages.application.prompt_budget (presupuesto adaptativo PA03)."""

from packages.application.prompt_budget import (
    _estimate_tokens,
    enforce_budget,
    tokens_to_chars,
    truncate_to_chars,
)


def test_tokens_to_chars():
    assert tokens_to_chars(4000) == 14000


def test_truncate_cuts_on_word():
    assert truncate_to_chars("hola mundo cruel", 10) == "hola…"


def test_truncate_short_unchanged():
    assert truncate_to_chars("corto", 100) == "corto"


def test_fixed_sections_reserved_intact():
    # El contenido fijo/determinista se reserva entero aunque el budget sea ínfimo.
    huge = "x" * 100000
    message = {
        "prompt_exacto_usuario": huge,
        "configuracion_creativa": {"canon": {"hard_rules": [huge]}},
        "contexto_autorizado": {"project_id": "p", "dato": huge},
    }
    out = enforce_budget(message, 100, {"vecindario": 1.0})
    assert out["prompt_exacto_usuario"] == huge
    assert out["configuracion_creativa"]["canon"]["hard_rules"] == [huge]
    assert out["contexto_autorizado"]["dato"] == huge


def test_flexible_section_trimmed_dropping_whole_items():
    items = [{"ref_id": f"e{i}", "rendered_text": "palabra " * 40} for i in range(20)]
    message = {"canon_confirmado": {"autoridad": "CANON", "items": items}}
    out = enforce_budget(message, 200, {"canon_confirmado": 1.0})
    kept = out["canon_confirmado"]["items"]
    assert 0 < len(kept) < 20
    # Items enteros: cada uno conserva su texto completo (no se parte a la mitad).
    assert all(it["rendered_text"] == "palabra " * 40 for it in kept)
    assert out["canon_confirmado"]["truncado"] is True


def test_waterfilling_redistributes_surplus_by_priority():
    # canon (alta prioridad) excede su 50%, pero el auxiliar (baja prioridad)
    # casi no usa el suyo: el sobrante fluye a canon y cabe entero (sin
    # water-filling se habría truncado).
    canon = {
        "autoridad": "CANON",
        "items": [{"ref_id": f"e{i}", "t": "palabra " * 12} for i in range(10)],
    }
    aux = {"autoridad": "RAG", "items": [{"ref_id": "d1", "t": "x"}]}
    message = {"canon_confirmado": canon, "rag_auxiliar": aux}

    canon_demand = _estimate_tokens(canon)
    aux_demand = _estimate_tokens(aux)
    total = canon_demand + aux_demand + 5  # pool justo para todo el contenido
    pct = {"canon_confirmado": 0.5, "rag_auxiliar": 0.5}

    out = enforce_budget(message, total, pct)
    assert "truncado" not in out["canon_confirmado"]
    assert len(out["canon_confirmado"]["items"]) == 10


def test_enforce_budget_does_not_mutate_input():
    big = "palabra " * 2000
    message = {"vecindario": {"items": [{"t": big}]}}
    before = message["vecindario"]["items"][0]["t"]
    enforce_budget(message, 1000, {"vecindario": 1.0})
    assert message["vecindario"]["items"][0]["t"] == before


def test_enforce_budget_missing_sections_ok():
    out = enforce_budget(
        {"directivas": None, "canon_confirmado": {}, "seleccion": "x"},
        4000,
        {"seleccion": 1.0},
    )
    assert "directivas" not in out
    assert "canon_confirmado" not in out
    assert out["seleccion"] == "x"
