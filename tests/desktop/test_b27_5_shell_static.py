from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_WINDOW = ROOT / "hosts" / "DesktopHostPySide" / "main_window.py"
CONTEXT = ROOT / "hosts" / "DesktopHostPySide" / "app_context.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
DESIGN = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "design_system.py"


def test_b27_5_shell_has_only_three_primary_sidebar_entries():
    text = MAIN_WINDOW.read_text(encoding="utf-8")
    assert '["Creación", "Galería", "Sesión"]' in text
    assert '"Dashboard"' not in text
    assert "DashboardView" not in text


def test_b27_5_project_actions_are_in_sidebar_configuration():
    text = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "Proyecto / Configuración" in text
    for label in ["Nuevo proyecto", "Abrir proyecto", "Guardar proyecto", "Cerrar proyecto", "Test IA"]:
        assert label in text


def test_b27_5_advanced_mode_state_exists_and_controls_debug_log():
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    ctx = CONTEXT.read_text(encoding="utf-8")
    assert "advanced_mode: bool = False" in ctx
    assert "Modo avanzado" in main
    assert "Diagnóstico" in main
    assert "self.log.setVisible(False)" in main
    assert "self.log.setVisible(bool(enabled) and self.ctx.advanced_mode)" in main


def test_b27_5_design_system_components_exist():
    text = DESIGN.read_text(encoding="utf-8")
    for symbol in ["APP_STYLESHEET", "class Card", "class Badge", "class AdvancedSection", "def human_ref"]:
        assert symbol in text


def test_b27_5_workspaces_group_existing_views_without_deleting_them():
    text = WORKSPACES.read_text(encoding="utf-8")
    for symbol in ["class CreationWorkspace", "class GalleryWorkspace", "class SessionWorkspace"]:
        assert symbol in text
    assert "Corpus técnico" in text
    assert "Relaciones técnicas" in text
    assert "Candidatos técnicos" in text
    assert "Campaña" in text and "Preparación" in text and "En vivo/Post" in text
