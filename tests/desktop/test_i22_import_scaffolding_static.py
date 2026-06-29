"""I22 — gating del andamiaje en el host desktop (chequeo estático).

Verifica el cableado de la secuencia en 2 fases sin levantar Qt: importar dispara
la propuesta de andamiaje (Fase 1), aplicar dispara la extracción (Fase 2), y la
extracción ya no auto-genera la config (generate_config=False).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPORT_VIEW = ROOT / "hosts" / "DesktopHostPySide" / "views" / "import_export_view.py"
IMPORT_CTRL = ROOT / "hosts" / "DesktopHostPySide" / "controllers" / "import_controller.py"
CONFIG_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "import_project_config_panel.py"


def test_controller_exposes_propose_scaffolding():
    text = IMPORT_CTRL.read_text(encoding="utf-8")
    assert "def propose_scaffolding(" in text
    assert "self.svc.propose_scaffolding(" in text


def test_extraction_no_longer_auto_generates_config():
    text = IMPORT_CTRL.read_text(encoding="utf-8")
    assert "generate_config=False" in text
    assert "generate_config=True" not in text


def test_import_triggers_scaffolding_first():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    # Al importar en modo Canon se propone el andamiaje, no la extracción directa.
    assert "def _start_scaffolding(" in text
    assert "self._start_scaffolding(basket.id)" in text


def test_applying_scaffolding_gates_extraction():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    # Aplicar el andamiaje (tarjeta o panel) dispara la Fase 2.
    accept = text.index("def _accept_config(")
    nxt = text.index("def _discard_config(")
    assert "self._start_extraction(basket_id)" in text[accept:nxt]
    # Y también desde el panel cuando la decisión es 'accept' (arranca la Fase 2
    # vía el runner persistente; las decisiones de volver/descartar reabren el menú).
    assert 'if decision == "accept":' in text
    assert "jobs.start_extraction(basket_id)" in text


def test_config_card_shows_rings_and_milestones():
    text = IMPORT_VIEW.read_text(encoding="utf-8")
    assert "anillo(s)" in text
    assert "hito(s)" in text


def test_config_panel_renders_rings_and_milestones():
    text = CONFIG_PANEL.read_text(encoding="utf-8")
    assert "Anillos (capas causales)" in text
    assert "Hitos en la cronología" in text
