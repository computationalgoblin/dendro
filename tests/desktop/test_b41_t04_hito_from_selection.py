"""Static tests for B41-T04: create hito from graph selection."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"


def test_b41_t04_creation_workspace_has_create_hito_from_selection():
    text = WORKSPACES.read_text(encoding="utf-8")
    assert "_create_hito_from_selection" in text, "Missing method _create_hito_from_selection in CreationWorkspace"


def test_b41_t04_selection_menu_includes_hito_option():
    text = WORKSPACES.read_text(encoding="utf-8")
    # The graph canvas context menu or action for creating hitos from selection
    assert "Hito desde selección" in text or "Crear hito explicativo" in text, \
        "Missing 'Hito desde selección' or 'Crear hito explicativo' menu action"


def test_b41_t04_hito_panel_prefills_from_selection():
    """CausalMilestonePanel must accept optional prefill data for entity/relation ids."""
    text = WORKSPACES.read_text(encoding="utf-8")
    # Panel should accept prefill argument
    assert "prefill" in text.lower() or "affected_entity_ids" in text or "affected_relation_ids" in text, \
        "CausalMilestonePanel should accept prefill data from selection"
