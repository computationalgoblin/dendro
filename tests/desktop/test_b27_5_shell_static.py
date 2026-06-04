from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_WINDOW = ROOT / "hosts" / "DesktopHostPySide" / "main_window.py"
CONTEXT = ROOT / "hosts" / "DesktopHostPySide" / "app_context.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
DESIGN = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "design_system.py"
HOME = ROOT / "hosts" / "DesktopHostPySide" / "views" / "home_view.py"


def test_b27_5_shell_keeps_three_product_spaces_without_dashboard():
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    for label in ["Creación", "Galería", "Sesión"]:
        assert label in main or label in home
    assert '"Dashboard"' not in main
    assert "DashboardView" not in main


def test_b31_project_and_config_are_corner_drawers_not_sidebar_labels():
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert "left_drawer" in main
    assert "RightDrawer" in main
    assert "config_menu" in main and "project_menu" in main
    assert "Proyecto / Configuración" not in main
    for label in ["Nuevo proyecto", "Abrir proyecto", "Guardar proyecto"]:
        assert label in main or label in home


def test_b32_advanced_mode_exists_but_diagnostic_is_not_normal_ui():
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    ctx = CONTEXT.read_text(encoding="utf-8")
    assert "advanced_mode: bool = False" in ctx
    assert "Modo avanzado" in main
    assert "self.log.setVisible(False)" in main
    assert "Diagnóstico" not in main
    assert "_topbar.setVisible(False)" in main


def test_b27_5_design_system_components_exist():
    text = DESIGN.read_text(encoding="utf-8")
    for symbol in ["APP_STYLESHEET", "class Card", "class Badge", "class AdvancedSection", "def human_ref"]:
        assert symbol in text


def test_b32_workspaces_keep_views_but_hide_technical_routes_from_normal_copy():
    text = WORKSPACES.read_text(encoding="utf-8")
    for symbol in ["class CreationWorkspace", "class GalleryWorkspace", "class SessionWorkspace"]:
        assert symbol in text
    assert "Taller narrativo" in text
    assert "Crear entidad" in text
    assert "Ir al grafo" in text
    assert "Importar documento" in text
    assert "Corpus técnico" not in text
    assert "Relaciones técnicas" not in text
    assert "Candidatos técnicos" not in text
    assert "Campaña" in text and "Preparación" in text and "En vivo/Post" in text
