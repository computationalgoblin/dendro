from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REL_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "relation_detail_panel.py"
AI_ACTIONS = ROOT / "packages" / "application" / "ai_context_actions.py"
CTX_BUILDER = ROOT / "packages" / "application" / "narrative_context_builder.py"


def test_relation_panel_has_b33_inline_ai_contract():
    text = REL_PANEL.read_text(encoding="utf-8")
    for phrase in [
        "Mejorar / desarrollar relación",
        "Sugerencia IA",
        "Generando sugerencia…",
        "Aceptar",
        "Descartar",
        "_RelationAIWorker(QThread)",
        "relation_text_suggestion",
        "_accept_suggestion",
        "_discard_suggestion",
        "_show_ai_error",
        "_safe_ai_error",
    ]:
        assert phrase in text
    assert "QColorDialog" not in text
    assert "run_relation_action" not in text
    assert "generate_candidates" not in text


def test_relation_panel_accepts_suggestion_into_user_editable_text_only():
    text = REL_PANEL.read_text(encoding="utf-8")
    assert "self.suggestion_text.toPlainText().strip()" in text
    assert "self.description_edit.setPlainText(text)" in text
    assert "self.body_edit.setPlainText(text)" in text
    assert "self.body_edit.setPlainText(current_body + \"\\n\\n\" + text)" in text
    # Accepting does not call controller.update directly; persistence happens only via save/autosave path.
    accept_body = text.split("def _accept_suggestion", 1)[1].split("def _discard_suggestion", 1)[0]
    assert "relation_controller.update" not in accept_body


def test_relation_panel_discard_and_error_do_not_modify_relation_fields():
    text = REL_PANEL.read_text(encoding="utf-8")
    discard_body = text.split("def _discard_suggestion", 1)[1].split("# ------------------------------------------------------------------", 1)[0]
    assert "self.suggestion_frame.setVisible(False)" in discard_body
    assert "self.suggestion_text.clear()" in discard_body
    assert "description_edit" not in discard_body
    assert "body_edit" not in discard_body

    error_body = text.split("def _show_ai_error", 1)[1].split("def _on_ai_finished", 1)[0]
    assert "Error IA:" in error_body
    assert "accept_btn.setEnabled(False)" in error_body
    assert "description_edit" not in error_body
    assert "body_edit" not in error_body


def test_relation_ai_prompt_uses_specific_contract_and_context():
    actions = AI_ACTIONS.read_text(encoding="utf-8")
    for phrase in [
        "relación narrativa entre dos entidades",
        "origen, ",
        "destino, tipo de relación, dirección, descripción, cuerpo, notas",
        "No devuelvas JSON",
        "No devuelvas una ficha técnica",
        "No crees entidades, relaciones, árboles, secretos ni canon nuevo",
        "source_full",
        "target_full",
        "Idioma:",
        "Género:",
        "Tono:",
        "Realismo:",
        "Estilo narrativo:",
        "Instrucción del usuario",
    ]:
        assert phrase in actions


def test_relation_context_builder_exposes_relation_text_and_full_endpoints():
    text = CTX_BUILDER.read_text(encoding="utf-8")
    for phrase in [
        '"source_full"',
        '"target_full"',
        '"body": meta.get("_body", "")',
        '"notes": meta.get("_notes", "")',
        '"creative_config"',
        '"primary_language"',
    ]:
        assert phrase in text
