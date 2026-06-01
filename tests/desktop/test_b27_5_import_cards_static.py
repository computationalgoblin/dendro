from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPORT_VIEW = ROOT / "hosts" / "DesktopHostPySide" / "views" / "import_export_view.py"


def test_b27_5_import_uses_import_candidates_defensively():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    assert 'getattr(basket, "import_candidates", [])' in text
    assert "basket.candidates" not in text


def test_b27_5_import_normal_mode_uses_cards_not_only_table():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    assert "Candidate card" not in text  # guard against stale doc-only marker
    assert "self.cards_container" in text
    assert "Card(_candidate_title(candidate)" in text
    assert "Aceptar" in text
    assert "Descartar" in text


def test_b27_5_import_hides_technical_data_behind_advanced_section():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    assert 'AdvancedSection("Datos técnicos / export")' in text
    assert "self.advanced.setVisible(bool(enabled))" in text
    assert "Datos técnicos — Modo avanzado" in text
    assert "Activa Modo avanzado" in text


def test_b27_5_import_no_raw_ids_in_clean_detail():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    start = text.index("    def _show_clean_detail")
    end = text.index("    def _show_detail_from_table")
    clean_detail = text[start:end]
    assert "basket_id" not in clean_detail
    assert "candidate_id" not in clean_detail
    assert "json.dumps" not in clean_detail
