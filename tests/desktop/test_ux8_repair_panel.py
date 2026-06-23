"""UX8 — panel de revisión de reparación (RepairReviewPanel).

Verifica que el panel muestra los cambios con antes/después, respeta las casillas,
devuelve el `after` editado y deshabilita los cambios no aplicables.
"""
from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.repair_review_panel import RepairReviewPanel

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _change(**kw):
    base = {"change_type": "edit_entity", "label": "X", "before": "antes",
            "after": "después", "applicable": True, "note": "", "text_field": "",
            "_change": {"change_type": "edit_entity"}}
    base.update(kw)
    return base


def test_panel_lists_changes_and_returns_selected(qapp):
    changes = [_change(label="A", after="texto A"), _change(label="B", after="texto B")]
    captured: list = []
    panel = RepairReviewPanel(changes, on_apply=lambda sel: captured.append(sel),
                              on_cancel=lambda: None)
    assert len(panel._rows) == 2
    # Desmarcar el segundo → solo se aplica el primero.
    panel._rows[1][1].setChecked(False)
    panel._apply()
    assert len(captured) == 1
    assert [c["label"] for c in captured[0]] == ["A"]


def test_panel_returns_edited_after_text(qapp):
    panel = RepairReviewPanel([_change(label="A", after="original")],
                              on_apply=lambda sel: None, on_cancel=lambda: None)
    _, _, editor = panel._rows[0]
    editor.setPlainText("editado por el usuario")
    selected = panel.selected_changes()
    assert selected[0]["after"] == "editado por el usuario"


def test_panel_disables_non_applicable_changes(qapp):
    changes = [_change(label="No existe", applicable=False, note="entidad ausente")]
    panel = RepairReviewPanel(changes, on_apply=lambda sel: None, on_cancel=lambda: None)
    change, check, editor = panel._rows[0]
    assert check.isChecked() is False
    assert check.isEnabled() is False
    assert editor is None  # sin editor para cambios no aplicables
    assert panel.selected_changes() == []


def test_panel_apply_requires_selection(qapp):
    panel = RepairReviewPanel([_change(applicable=False)],
                              on_apply=lambda sel: pytest.fail("no debe aplicar"),
                              on_cancel=lambda: None)
    panel._apply()  # nada seleccionable → muestra aviso, no llama on_apply
    assert "Marca al menos" in panel._status.text()
