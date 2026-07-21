from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py"
AI_PROVIDER = ROOT / "packages" / "infrastructure" / "ai_provider.py"
CONTRACT = ROOT / "docs" / "contracts" / "b32-ai-action-boundaries.md"


def test_entity_and_tree_inline_ai_use_text_suggestion_only():
    # BETA2-CLEANUP-PANELES: TreeDetailPanel se retiró; la edición de ramas
    # (incl. IA inline) vive en el Foco vía NodeDetailPanel (variant="foco").
    for path in [NODE_PANEL]:
        text = path.read_text(encoding="utf-8")
        assert "node_text_suggestion" in text
        assert 'run_node_action("improve_text"' not in text
        assert "generate_candidates(" not in text


def test_generic_english_rewrite_stub_is_not_present():
    text = AI_PROVIDER.read_text(encoding="utf-8")
    assert "Rewritten description in a different style" not in text


def test_ai_boundaries_surface_removed():
    # El contrato b32-ai-action-boundaries.md acotaba la superficie de acciones
    # IA contextuales/inline; esa superficie se BORRÓ en la limpieza post-WIKI
    # (2026-07-21). La frontera vigente es la ausencia del módulo: la IA solo
    # entra por Regar/Sugerencias/wiki/cronología y nunca escribe canon.
    assert not (ROOT / "packages" / "application" / "ai_context_actions.py").exists()
    assert not CONTRACT.exists()  # el contrato retirado no debe resucitar solo
