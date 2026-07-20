"""Static contract tests for B32 — semantic tree containers.

These tests verify structural contracts without importing PySide6 (no GUI).
They validate: TreeMeta integration, container entity support, graph canvas API,
workspaces routing, tree detail panel API, and narrative context builder extensions.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ─── Helpers ────────────────────────────────────────────────────────────

def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _tree(rel: str) -> ast.Module:
    return ast.parse(_src(rel))


def _names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _class_methods(tree: ast.Module, cls_name: str) -> set[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            return {
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def _class_init_vars(tree: ast.Module, cls_name: str) -> set[str]:
    """Extract self.X variable names from __init__ body."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    names = set()
                    for stmt in item.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if (isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"):
                                    names.add(target.attr)
                        if isinstance(stmt, ast.AnnAssign):
                            if isinstance(stmt.target, ast.Attribute):
                                names.add(stmt.target.attr)
                            elif isinstance(stmt.target, ast.Name):
                                names.add(stmt.target.id)
                    return names
    return set()


# ─── T1: Domain EntityType includes CONTENEDOR ─────────────────────────

def test_entity_type_has_contenedor():
    src = _src("packages/domain/entity.py")
    assert "CONTENEDOR" in src, "EntityType debe incluir CONTENEDOR"
    assert '"contenedor"' in src, "EntityType.CONTENEDOR value debe ser 'contenedor'"


def test_schema_v21():
    src = _src("packages/persistence/schema.py")
    assert "CURRENT_SCHEMA_VERSION: int = 21" in src, "Schema debe ser v21"


def test_migration_v20_to_v21_exists():
    src = _src("packages/persistence/schema.py")
    assert "_apply_migration_v20_to_v21" in src, "Debe existir migracion v20→v21"


def test_store_imports_migration():
    src = _src("packages/persistence/store.py")
    assert "_apply_migration_v20_to_v21" in src, "Store debe importar migracion v20→v21"
    assert "version == 20" in src, "Store debe aplicar migracion cuando version == 20"


# ─── T3: GraphTreeItem class exists ────────────────────────────────────

def test_graph_tree_item_class():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    names = _names(tree)
    assert "GraphTreeItem" in names, "GraphTreeItem debe existir"


def test_graph_tree_item_methods():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    methods = _class_methods(tree, "GraphTreeItem")
    expected = {"set_drag_highlight", "set_coherence_selected", "paint", "add_child_node", "resize_to_fit_children"}
    assert expected <= methods, f"GraphTreeItem debe tener metodos {expected}, tiene {methods}"


def test_graph_tree_item_inherits_rect():
    src = _src("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    assert "class GraphTreeItem(QGraphicsRectItem)" in src, "GraphTreeItem debe heredar de QGraphicsRectItem"


# ─── T4-T7: GraphCanvasView extended API ───────────────────────────────

def test_canvas_has_trees_dict():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    attrs = _class_init_vars(tree, "GraphCanvasView")
    assert "_trees" in attrs, "GraphCanvasView debe tener _trees dict"


def test_canvas_has_membership_dict():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    attrs = _class_init_vars(tree, "GraphCanvasView")
    assert "_membership" in attrs, "GraphCanvasView debe tener _membership dict"


def test_canvas_has_alt_drag_state():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    attrs = _class_init_vars(tree, "GraphCanvasView")
    assert "_alt_source" in attrs, "GraphCanvasView debe tener _alt_source"
    assert "_alt_line" in attrs, "GraphCanvasView debe tener _alt_line"


def test_canvas_has_cycle_check():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    methods = _class_methods(tree, "GraphCanvasView")
    assert "would_create_cycle" in methods, "GraphCanvasView debe tener would_create_cycle"


def test_canvas_has_tree_container_for():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    methods = _class_methods(tree, "GraphCanvasView")
    assert "tree_container_for" in methods, "GraphCanvasView debe tener tree_container_for"


def test_canvas_has_alt_drag_methods():
    tree = _tree("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    methods = _class_methods(tree, "GraphCanvasView")
    expected = {"_start_alt_drag", "_update_alt_drag", "_finish_alt_drag", "_item_tree_at"}
    assert expected <= methods, f"Faltan metodos alt-drag: {expected - methods}"


def test_canvas_node_assign_signal():
    src = _src("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    assert "nodeAssignToTreeRequested = Signal" in src, "Signal nodeAssignToTreeRequested debe existir"


def test_canvas_widget_forwards_signal():
    src = _src("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    # GraphCanvasWidget must have the signal AND connect it
    lines = src.split("\n")
    in_widget = False
    has_signal = False
    has_connect = False
    for line in lines:
        if "class GraphCanvasWidget" in line:
            in_widget = True
        if in_widget:
            if "nodeAssignToTreeRequested = Signal" in line:
                has_signal = True
            if "nodeAssignToTreeRequested.connect" in line:
                has_connect = True
    assert has_signal, "GraphCanvasWidget debe declarar nodeAssignToTreeRequested"
    assert has_connect, "GraphCanvasWidget debe conectar nodeAssignToTreeRequested"


def test_node_colors_has_contenedor():
    src = _src("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    assert '"contenedor"' in src.split("_NODE_COLORS")[1].split("}")[0], "_NODE_COLORS debe incluir contenedor"


# ─── T8: Tree detail panel — RETIRADO (BETA2-CLEANUP-PANELES) ──────────
# El cajón de rama (TreeDetailPanel) se eliminó: la edición de ramas vive
# ahora en el Modo Foco (NodeDetailPanel variant="foco").

def test_tree_detail_panel_removed():
    p = ROOT / "hosts/DesktopHostPySide/widgets/tree_detail_panel.py"
    assert not p.exists(), "tree_detail_panel.py debe estar eliminado (edición en Foco)"


# ─── T9: Workspaces integration ────────────────────────────────────────

def test_workspaces_has_create_tree():
    tree = _tree("hosts/DesktopHostPySide/views/workspaces.py")
    methods = _class_methods(tree, "CreationWorkspace")
    assert "_create_tree_on_graph" in methods, "CreationWorkspace debe tener _create_tree_on_graph"


def test_workspaces_no_open_tree_panel():
    # BETA2-CLEANUP-PANELES: el cajón de rama se retiró; ya no debe existir
    # _open_tree_panel (la edición de ramas ocurre en el Modo Foco).
    tree = _tree("hosts/DesktopHostPySide/views/workspaces.py")
    methods = _class_methods(tree, "CreationWorkspace")
    assert "_open_tree_panel" not in methods, "CreationWorkspace ya no debe abrir el cajón de rama"


def test_workspaces_has_assign_node():
    tree = _tree("hosts/DesktopHostPySide/views/workspaces.py")
    methods = _class_methods(tree, "CreationWorkspace")
    assert "_assign_node_to_tree" in methods, "CreationWorkspace debe tener _assign_node_to_tree"


def test_workspaces_routes_contenedor():
    src = _src("hosts/DesktopHostPySide/views/workspaces.py")
    assert "contenedor" in src, "Workspaces debe manejar contenedor en routing"


def test_workspaces_connects_assign_signal():
    src = _src("hosts/DesktopHostPySide/views/workspaces.py")
    assert "nodeAssignToTreeRequested.connect" in src, "Workspaces debe conectar nodeAssignToTreeRequested"


def test_workspaces_create_tree_button():
    src = _src("hosts/DesktopHostPySide/views/workspaces.py")
    assert "⊞" in src, "Workspaces debe tener boton ⊞ para crear contenedor"
    assert "Crear contenedor" in src, "Boton debe tener tooltip 'Crear contenedor'"


# ─── T10: Narrative context builder has tree_membership ────────────────

def test_context_builder_tree_membership():
    src = _src("packages/application/narrative_context_builder.py")
    assert "tree_membership" in src, "Context builder debe incluir tree_membership"
    assert "contiene" in src, "Context builder debe buscar relaciones contiene"


# ─── T11: All modified files compile ───────────────────────────────────

def test_all_files_compile():
    """Verify all key files are syntactically valid."""
    files = [
        "packages/domain/entity.py",
        "packages/persistence/schema.py",
        "packages/persistence/store.py",
        "packages/application/narrative_context_builder.py",
        "hosts/DesktopHostPySide/widgets/graph_canvas.py",
        "hosts/DesktopHostPySide/views/workspaces.py",
    ]
    for rel in files:
        path = ROOT / rel
        assert path.exists(), f"{rel} debe existir"
        ast.parse(path.read_text(encoding="utf-8"), filename=rel)


# ─── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS  {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {test.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {test.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} assertions passed")
    if failed:
        sys.exit(1)
