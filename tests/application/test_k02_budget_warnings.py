"""BETA1-K02 / fila 34: el recorte por presupuesto deja de ser silencioso.

`enforce_budget_report` devuelve un aviso por cada sección flexible recortada;
`enforce_budget` mantiene el contrato antiguo (solo el mensaje).
"""
from __future__ import annotations

from packages.application.prompt_budget import enforce_budget, enforce_budget_report


def _message_with_big_canon():
    return {
        "prompt_exacto_usuario": "haz algo",  # fija/sagrada, se reserva entera
        "canon_confirmado": {
            "autoridad": "canon",
            "items": [
                {"ref_id": str(i), "rendered_text": "palabra " * 40} for i in range(20)
            ],
        },
    }


def test_report_warns_when_section_truncated():
    message = _message_with_big_canon()
    result, warnings = enforce_budget_report(
        message, total_budget_tokens=120, section_percentages={"canon_confirmado": 1.0}
    )
    assert warnings, "debería avisar del recorte de canon"
    assert any("canon" in w for w in warnings)
    assert result["canon_confirmado"].get("truncado") is True
    # No muta la entrada original.
    assert len(message["canon_confirmado"]["items"]) == 20


def test_no_warning_when_everything_fits():
    message = _message_with_big_canon()
    result, warnings = enforce_budget_report(
        message, total_budget_tokens=100_000, section_percentages={"canon_confirmado": 1.0}
    )
    assert warnings == []
    assert "truncado" not in result["canon_confirmado"]


def test_enforce_budget_shim_returns_only_dict():
    message = _message_with_big_canon()
    only_dict = enforce_budget(
        message, 120, section_percentages={"canon_confirmado": 1.0}
    )
    from_report, _ = enforce_budget_report(
        message, 120, section_percentages={"canon_confirmado": 1.0}
    )
    assert only_dict == from_report
    assert isinstance(only_dict, dict)
