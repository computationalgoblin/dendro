"""BETA1-K02 / fila 33: badge de fuente + diff antes/después en la revisión.

- `source_badge_text` distingue origen (usuario/IA/importación) y confianza.
- Un candidato de edición muestra el valor actual de canon (read-only) para comparar.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QTextEdit

from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    source_badge_text,
)


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _cand(**kw):
    base = dict(
        candidate_type=SimpleNamespace(value="cambio"),
        title="Editar Aurora",
        source="ai_command_bar",
        confidence=0.62,
        proposed_data={},
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ── badge de fuente ──────────────────────────────────────────────────────────
def test_source_badge_ia_con_confianza():
    text = source_badge_text(_cand(source="ai_command_bar", confidence=0.62))
    assert "IA" in text
    assert "62%" in text


def test_source_badge_usuario_y_origen_desconocido():
    # La rama "Importación" se retiró con el subsistema de import (BETA1-CLEANUP-IMPORT):
    # un source residual de import cae al origen genérico, sin badge especial.
    assert "Importación" not in source_badge_text(_cand(source="import_review", confidence=None))
    assert "Usuario" in source_badge_text(_cand(source="manual", confidence=None))


# ── diff antes/después ───────────────────────────────────────────────────────
def _controller_with_entity(name, value):
    entity = SimpleNamespace(
        id="e1", name=name, extended_description=value,
        brief_description="", description="", summary="",
    )
    project = SimpleNamespace(entities=[entity])
    return SimpleNamespace(ps=SimpleNamespace(active_project=project))


def test_edit_candidate_shows_canon_before_value():
    cand = _cand(
        proposed_data={
            "edit_proposed_value": "texto nuevo propuesto",
            "edit_target_name": "Aurora",
            "edit_field": "body",
        }
    )
    ctrl = _controller_with_entity("Aurora", "valor viejo en canon")
    panel = CandidateReviewPanel(cand, ctrl)
    readonly_texts = [
        w.toPlainText()
        for w in panel.findChildren(QTextEdit)
        if w.isReadOnly()
    ]
    assert any("valor viejo en canon" in t for t in readonly_texts)


def test_edit_candidate_without_target_has_no_before_box():
    cand = _cand(
        proposed_data={
            "edit_proposed_value": "texto nuevo",
            "edit_target_name": "NoExiste",
            "edit_field": "body",
        }
    )
    ctrl = _controller_with_entity("Aurora", "valor viejo")
    panel = CandidateReviewPanel(cand, ctrl)
    readonly_texts = [
        w.toPlainText() for w in panel.findChildren(QTextEdit) if w.isReadOnly()
    ]
    assert not any("valor viejo" in t for t in readonly_texts)
