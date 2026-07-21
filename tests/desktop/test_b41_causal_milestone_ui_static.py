from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
CONTROLLER = ROOT / "hosts" / "DesktopHostPySide" / "controllers" / "causal_milestone_controller.py"


def test_b41_creation_workspace_exposes_create_hito_button_and_panel():
    text = WORKSPACES.read_text(encoding="utf-8")

    assert "Crear hito" in text
    assert "CausalMilestonePanel" in text
    assert "_open_hito_panel" in text
    # (el pin de `_milestone_btn` se retiró: el botón dedicado de la toolbar
    # desapareció en los rediseños BETA1/2; el panel se abre por _open_hito_panel)


def test_b41_hito_ui_uses_cards_not_technical_table_or_json():
    text = WORKSPACES.read_text(encoding="utf-8")
    start = text.index("class CausalMilestonePanel")
    panel = text[start:text.index("class CreationWorkspace", start)]

    assert "Card(" in panel
    assert "QTable" not in panel
    # Strip docstrings before checking for JSON — the docstring mentions "no JSON"
    import re
    code_only = re.sub(r'""".*?"""', '', panel, flags=re.DOTALL)
    assert "JSON" not in code_only
    # No raw IDs shown to user — only title/type/description
    assert "\"id\"" not in code_only


def test_b41_ui_routes_through_application_controller_service():
    controller_text = CONTROLLER.read_text(encoding="utf-8")
    workspace_text = WORKSPACES.read_text(encoding="utf-8")

    assert "CausalMilestoneService" in controller_text
    assert "create_manual" in controller_text
    assert "project.causal_milestones.append" not in workspace_text
    assert "CausalMilestoneController" in workspace_text
