from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "graph_canvas.py"
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
REL_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "relation_detail_panel.py"
REL_SERVICE = ROOT / "packages" / "application" / "relation_service.py"


def test_graph_drag_emits_visual_relation_create_and_rejection_paths():
    text = GRAPH.read_text(encoding="utf-8")
    assert "relationCreateRequested = Signal(str, str)" in text
    assert "relationCreateRejected = Signal(str)" in text
    assert "_start_relation_drag" in text
    assert "_update_relation_drag" in text
    assert "_finish_relation_drag" in text
    assert "_relation_drag_arrow_path" in text
    assert "QGraphicsPathItem" in text
    assert "Flecha provisional de relación" in text
    assert "set_drag_highlight(True)" in text
    assert "No se puede crear una relación sobre el mismo elemento" in text
    assert "Relación cancelada" in text


def test_creation_workspace_creates_draft_and_opens_relation_detail_panel_directly():
    text = WORKSPACES.read_text(encoding="utf-8")
    assert "RelationCreatePanel" not in text
    assert "_open_relation_create_panel" in text
    assert '"_visual_draft": True' in text
    assert "_open_relation_panel(relation_id, is_new=True)" in text
    assert "Ya existe una relación entre esas entidades" in text
    assert "source_id == target_id" in text


def test_relation_panel_supports_required_normal_fields_and_no_external_windows():
    text = REL_PANEL.read_text(encoding="utf-8")
    for phrase in [
        "Origen → destino",
        "Destino → origen",
        "Bidireccional",
        "Descripción:",
        "Cuerpo:",
        "Notas:",
        "Color de la arista",
        "_visual_draft",
        "relation_controller.delete",
        "source_id, target_id = target_id, source_id",
    ]:
        assert phrase in text
    assert "QColorDialog" not in text
    assert "Datos técnicos" in text


def test_relation_service_updates_real_domain_fields_for_visual_relation():
    text = REL_SERVICE.read_text(encoding="utf-8")
    for phrase in [
        '"source_id"',
        '"target_id"',
        '"relation_type"',
        '"direction"',
        '"custom_metadata"',
        "_normalize_relation_enums",
    ]:
        assert phrase in text
