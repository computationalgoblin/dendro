"""Tests para packages.application.prompt_budget (M7)."""

from packages.application.prompt_budget import (
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


def test_enforce_budget_section_limits():
    big = "palabra " * 2000  # ~16000 chars
    message = {
        "directivas": big,        # 4% → 560 chars máx
        "cerco_canon": big,       # 14% → 1960 chars máx
        "vecindario": big,        # 20% → 2800 chars máx
    }
    out = enforce_budget(message, 4000)
    assert len(out["directivas"]) <= 560 + 2
    assert len(out["cerco_canon"]) <= 1960 + 2
    assert len(out["vecindario"]) <= 2800 + 2


def test_enforce_budget_keeps_user_prompt_intact():
    huge = "x" * 100000
    message = {"prompt_exacto_usuario": huge, "cerco_canon": huge}
    out = enforce_budget(message, 1000)
    assert out["prompt_exacto_usuario"] == huge  # sagrado: nunca se trunca
    assert len(out["cerco_canon"]) < len(huge)   # sí se trunca


def test_enforce_budget_does_not_mutate_input():
    big = "palabra " * 2000
    message = {"vecindario": big}
    before = message["vecindario"]
    enforce_budget(message, 1000)
    assert message["vecindario"] == before


def test_enforce_budget_missing_sections_ok():
    # No explota si faltan secciones y omite las vacías/None.
    out = enforce_budget({"directivas": None, "cerco_canon": {}, "seleccion": "x"}, 4000)
    assert "directivas" not in out
    assert "cerco_canon" not in out
    assert out["seleccion"] == "x"
