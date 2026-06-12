"""D04/D06 AI UX contract in Creation."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_d06_creation_toolbar_hides_redundant_ai_actions():
    text = _read("hosts/DesktopHostPySide/views/workspaces.py")

    assert "_suggest_entity_btn" in text
    assert "_suggest_branch_btn" in text
    assert "_suggest_relation_btn" in text
    assert "_coherence_btn" in text
    assert "_summary_btn" in text
    assert "_jobs_btn" in text
    assert "ai_button.setVisible(False)" in text


def test_d06_contextual_ai_actions_route_to_reviewable_jobs():
    workspace = _read("hosts/DesktopHostPySide/views/workspaces.py")
    canvas = _read("hosts/DesktopHostPySide/widgets/graph_canvas.py")

    assert "def _launch_toolbar_ai_job" in workspace
    assert "def _run_context_ai_action" in workspace
    assert "contextAIActionRequested.connect(self._run_context_ai_action)" in workspace
    assert "contextAIActionRequested = Signal(str)" in canvas
    assert "IA sobre seleccion" in canvas
    assert "suggest_nodes" in canvas
    assert "suggest_branches" in canvas
    assert "suggest_relations" in canvas
    assert "analyze_coherence" in canvas


def test_d06_detail_panels_expose_single_ai_prompt():
    node_panel = _read("hosts/DesktopHostPySide/widgets/node_detail_panel.py")
    tree_panel = _read("hosts/DesktopHostPySide/widgets/tree_detail_panel.py")
    relation_panel = _read("hosts/DesktopHostPySide/widgets/relation_detail_panel.py")

    assert "self.ai_generate_btn.setText(\"Consultar\")" in node_panel
    assert "extra_ai_widget.setVisible(False)" in node_panel

    assert "self.ai_run_btn = QPushButton(\"Consultar\")" in tree_panel
    assert "self.ai_prompt_edit" in tree_panel
    assert "extra_ai_widget.setVisible(False)" in tree_panel

    assert "self.ai_generate_btn.setText(\"Consultar\")" in relation_panel
    assert "self.ai_coherence_btn.setVisible(False)" in relation_panel
    assert "self.refine_btn.setVisible(True)" in relation_panel


def test_d06_context_menu_preserves_multiselection_for_ai():
    canvas = _read("hosts/DesktopHostPySide/widgets/graph_canvas.py")

    assert "if node.node.entity_id not in self._selected_entity_ids" in canvas
    assert "if edge.edge.relation_id not in self._selected_relation_ids" in canvas
