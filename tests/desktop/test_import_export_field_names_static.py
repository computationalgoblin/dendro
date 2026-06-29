from __future__ import annotations

from pathlib import Path


def test_import_export_view_uses_real_import_model_field_names_only():
    text = Path("hosts/DesktopHostPySide/views/import_export_view.py").read_text(encoding="utf-8")

    # Campos reales del modelo B17 que la vista sigue usando.
    assert "import_candidates" in text
    assert "proposed_data" in text

    # No deben aparecer nombres de campo legacy (la guardia importante).
    assert "basket.candidates" not in text
    assert "source_segment_id" not in text
    assert "proposed_payload" not in text
    assert "duplicate_of_entity_ids" not in text
