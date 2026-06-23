"""UX3 · Vista previa de contexto: el panel recoge exclusiones correctamente."""
from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _preview():
    # Estructura tal y como la devuelve build_context_preview.
    return {
        "intent": "suggest_relations",
        "tier": "causal",
        "input_budget": 40000,
        "total_tokens": 120,
        "sections": [
            {"key": "prompt_exacto_usuario", "label": "Tu petición", "fixed": True,
             "est_tokens": 10, "truncado": False, "items": []},
            {"key": "canon_confirmado", "label": "Canon confirmado", "fixed": False,
             "est_tokens": 80, "truncado": True, "items": [
                 {"ref_id": "e1", "kind": "entity", "est_tokens": 40, "text": "Ariadna"},
                 {"ref_id": "e2", "kind": "entity", "est_tokens": 40, "text": "Devian"},
             ]},
            {"key": "cronologia", "label": "Cronología", "fixed": False,
             "est_tokens": 30, "truncado": False, "items": []},
        ],
    }


def _panel(qapp, captured):
    from hosts.DesktopHostPySide.widgets.context_preview_panel import ContextPreviewPanel

    return ContextPreviewPanel(
        _preview(),
        on_apply=lambda secs, items: captured.update(sections=secs, items=items),
    )


def test_fixed_sections_have_no_excludable_checkbox(qapp):
    captured = {}
    panel = _panel(qapp, captured)
    # La sección fija no se registra como excluible.
    assert "prompt_exacto_usuario" not in panel._section_checks
    assert "canon_confirmado" in panel._section_checks
    assert "cronologia" in panel._section_checks


def test_unchecking_item_marks_it_excluded(qapp):
    captured = {}
    panel = _panel(qapp, captured)
    panel._item_checks["e1"].setChecked(False)
    sections, items = panel.excluded()
    assert items == ["e1"]
    assert sections == []


def test_unchecking_section_marks_it_excluded(qapp):
    captured = {}
    panel = _panel(qapp, captured)
    panel._section_checks["cronologia"].setChecked(False)
    sections, items = panel.excluded()
    assert sections == ["cronologia"]


def test_apply_callback_receives_exclusions(qapp):
    captured = {}
    panel = _panel(qapp, captured)
    panel._section_checks["canon_confirmado"].setChecked(False)
    panel._item_checks["e2"].setChecked(False)
    panel._emit_apply()
    assert captured["sections"] == ["canon_confirmado"]
    assert captured["items"] == ["e2"]
