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
    base_mark_text,
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
        source="ai_suggest_composite",
        confidence=0.62,
        proposed_data={},
        metadata={},
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ── badge de fuente ──────────────────────────────────────────────────────────
def test_source_badge_ia_con_confianza_declarada():
    """BETA-MULTIAGENT2-FIX-08 (G2-13): el porcentaje solo se pinta si la confianza
    la DECLARÓ el modelo. El 0,62 literal del código no se enseña como medida."""
    declarada = _cand(confidence=0.62, metadata={"confianza_declarada": True})
    text = source_badge_text(declarada)
    assert "IA" in text
    assert "62%" in text
    assert "declarada" in text


def test_source_badge_sin_senal_declarada_no_pinta_porcentaje():
    text = source_badge_text(_cand(confidence=0.62, metadata={}))
    assert "IA" in text
    assert "%" not in text


# ── marca de base (canon / inferido / inventado) ─────────────────────────────
def test_base_mark_text_muestra_la_marca_declarada():
    text = base_mark_text(_cand(metadata={"base": "inventado", "base_nota": "sin canon"}))
    assert "invención" in text
    assert "sin canon" in text
    assert base_mark_text(_cand(metadata={"base": "no_declarada"})).startswith("Base:")
    # Sin familia que declare base, no se pinta fila hueca (ni se inventa la marca).
    assert base_mark_text(_cand(metadata={})) == ""


def test_panel_muestra_la_fila_de_base():
    from PySide6.QtWidgets import QLabel

    cand = _cand(metadata={"base": "canon", "base_nota": "consta en la crónica"})
    panel = CandidateReviewPanel(cand, _controller_with_entity("Aurora", "x"))
    textos = [w.text() for w in panel.findChildren(QLabel)]
    assert any("Base:" in t and "consta en la crónica" in t for t in textos)


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


def test_multi_field_patch_renders_row_per_field_and_collects_types():
    """PLAY-15: un patch edit_fields muestra una fila por campo (before/after)
    y al aceptar recoge los valores editados conservando el tipo original."""
    cand = _cand(
        proposed_data={
            "edit_kind": "entity_edits",
            "edit_target_name": "Aurora",
            "edit_fields": {"name": "Aurora la Roja", "birth_year": -80},
        }
    )
    ctrl = _controller_with_entity("Aurora", "cuerpo en canon")
    panel = CandidateReviewPanel(cand, ctrl)

    assert set(panel._field_edits) == {"name", "birth_year"}
    editor, _original = panel._field_edits["birth_year"]
    editor.setPlainText("-90")
    panel._apply_edits()

    assert cand.proposed_data["edit_fields"]["birth_year"] == -90  # int conservado
    assert cand.proposed_data["edit_fields"]["name"] == "Aurora la Roja"


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
