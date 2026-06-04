from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py"
TREE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "tree_detail_panel.py"
AI_PROVIDER = ROOT / "packages" / "infrastructure" / "ai_provider.py"
CONTRACT = ROOT / "docs" / "contracts" / "b32-ai-action-boundaries.md"


def test_entity_and_tree_inline_ai_use_text_suggestion_only():
    for path in [NODE_PANEL, TREE_PANEL]:
        text = path.read_text(encoding="utf-8")
        assert "node_text_suggestion" in text
        assert 'run_node_action("improve_text"' not in text
        assert "generate_candidates(" not in text


def test_generic_english_rewrite_stub_is_not_present():
    text = AI_PROVIDER.read_text(encoding="utf-8")
    assert "Rewritten description in a different style" not in text


def test_ai_boundaries_contract_exists():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in [
        "IA inline",
        "Candidatos globales IA",
        "Importación documental",
        "Diagnóstico/incidencias",
        'run_node_action("improve_text")',
    ]:
        assert phrase in text
