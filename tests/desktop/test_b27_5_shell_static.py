from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_WINDOW = ROOT / "hosts" / "DesktopHostPySide" / "main_window.py"
CONTEXT = ROOT / "hosts" / "DesktopHostPySide" / "app_context.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
DESIGN = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "design_system.py"
HOME = ROOT / "hosts" / "DesktopHostPySide" / "views" / "home_view.py"


def test_b27_5_shell_keeps_three_product_spaces_without_dashboard():
    # BETA1: legacy test name, new contract is Home + Creation only (A04).
    # Pre-BETA1 this test asserted a three-space shell (Creación/Galería/
    # Sesión). BETA 1 reduces the runtime shell to Home + Creación; Gallery
    # and Session code was physically removed from Desktop in BETA1-H02.
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    # Creation remains reachable from the shell
    assert "Creación" in main or "Creación" in home
    assert "creation_card" in home
    # Gallery/Session are out of the BETA1 runtime: no instantiation, no
    # cards, no navigation wiring (instantiation patterns with "(" so that
    # explanatory comments do not produce false positives)
    assert "GalleryWorkspace(" not in main
    assert "SessionWorkspace(" not in main
    assert "SessionPreparationWorkspace(" not in main
    assert "gallery_card" not in home
    assert "session_card" not in home
    assert 'register_callback("navigate_gallery"' not in main
    assert 'register_callback("navigate_session"' not in main
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
    # BETA2-UX-02: el topbar técnico (siempre oculto) se eliminó; el modo
    # avanzado ya no expone superficie visible (badge/topbar) — solo el log
    # de diagnóstico, que permanece oculto en modo normal.
    assert "_build_topbar" not in main
    assert "_advanced_badge" not in main


def test_b27_5_design_system_components_exist():
    text = DESIGN.read_text(encoding="utf-8")
    for symbol in ["APP_STYLESHEET", "class Card", "class Badge", "class AdvancedSection", "def human_ref"]:
        assert symbol in text


def test_b32_workspaces_keep_views_but_hide_technical_routes_from_normal_copy():
    text = WORKSPACES.read_text(encoding="utf-8")
    assert "class CreationWorkspace" in text
    for legacy_symbol in ["class GalleryWorkspace", "class SessionWorkspace", "class SessionPreparationWorkspace", "class SessionOverview"]:
        assert legacy_symbol not in text
    assert "Taller narrativo" in text
    assert "Crear hoja" in text
    assert "Ir al grafo" in text
    assert "Importar documento" in text
    assert "Corpus técnico" not in text
    assert "Relaciones técnicas" not in text
    assert "Candidatos técnicos" not in text
    assert "Campaña" not in text and "Preparación" not in text and "En vivo/Post" not in text
