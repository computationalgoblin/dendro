from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_b31_creation_t03_joint_coherence_ui_contract():
    workspaces = _read("hosts/DesktopHostPySide/views/workspaces.py")
    graph = _read("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    panel = _read("hosts/DesktopHostPySide/widgets/coherence_panel.py")
    controller = _read("hosts/DesktopHostPySide/controllers/ai_context_controller.py")
    service = _read("packages/application/ai_context_actions.py")
    builder = _read("packages/application/narrative_context_builder.py")

    assert 'QPushButton("⚖")' in workspaces
    assert "_open_coherence_panel" in workspaces
    assert "CoherencePanel(" in workspaces
    assert "graphSelectionChanged = Signal(list, list)" in graph
    assert "Qt.KeyboardModifier.ControlModifier" in graph
    assert "def selected_entity_ids" in graph
    assert "def selected_relation_ids" in graph
    assert "def clear_selection" in graph
    assert "class _CoherenceAIWorker(QThread)" in panel
    assert "def _accept_repair" in panel
    assert ".create(" not in panel
    assert "create_relation" not in panel
    assert "def analyze_coherence" in controller
    assert "def repair_coherence" in controller
    assert "run_selection_coherence_analysis" in service
    assert "run_selection_coherence_repair" in service
    assert "No debes crear entidades ni relaciones" in service
    assert "nearby_context" in builder
