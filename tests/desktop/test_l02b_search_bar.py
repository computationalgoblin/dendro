"""BETA1-L02b — barra de búsqueda flotante 'd': búsqueda unificada + navegación.

`_unified_search(q)` mezcla entidades del grafo (graph.search) con hitos de la
cronología (filtrados por título) y los rankea (prefijo de título primero).
`_navigate_search_item` salta a la mejor: grafo → asegura vista concéntrica y
`focus_search_result`; hito → cambia a cronología y `center_on_milestone`.

Se construye el workspace con __new__ + dobles ligeros para aislar la lógica (el
constructor real de CreationWorkspace es pesado y abre toda la UI)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401  (marca disponibilidad de Qt)

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphSearchResult

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(autouse=True)
def _qapp():
    # Necesario para que QTimer.singleShot (re-centrado diferido del hito) sea seguro.
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _entity_result(item_id, title):
    return GraphSearchResult(
        item_id=item_id,
        item_kind="entity",
        title=title,
        type_label="Concepto",
        category="Entidad",
    )


def _milestone(mid, title):
    return SimpleNamespace(id=mid, title=title, milestone_type=SimpleNamespace(value="pacto"))


class _FakeGraph:
    def __init__(self, results):
        self._results = results
        self.focused = []

    def search(self, query):
        q = query.lower()
        return [r for r in self._results if q in r.title.lower()]

    def focus_relation(self, item_id):
        self.focused.append(("relation", item_id))
        return True

    def focus_tree(self, item_id):
        self.focused.append(("tree", item_id))
        return True

    def focus_node(self, item_id):
        self.focused.append(("node", item_id))
        return True


class _FakeChrono:
    def __init__(self):
        self.centered = []

    def center_on_milestone(self, mid):
        self.centered.append(mid)
        return True


class _FakeCtrl:
    def __init__(self, milestones):
        self._milestones = milestones

    def list_all(self):
        return list(self._milestones)


def _workspace(entities, milestones, active_view="concentric"):
    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws.graph = _FakeGraph(entities)
    ws.chrono = _FakeChrono()
    ws._milestone_ctrl = _FakeCtrl(milestones)
    ws._active_view = active_view
    ws._view_switches = []
    # BETA1-L02c: estado del debounce de la barra (sin Qt real en estos tests).
    ws._float_search = None
    ws._search_nav_timer = None
    ws._search_pending_item = None
    # Sustituye set_active_view por un doble que registra y actualiza el estado.
    ws.set_active_view = lambda view: (
        ws._view_switches.append(view),
        setattr(ws, "_active_view", "chrono" if view == "chrono" else "concentric"),
    )
    return ws


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_unified_search_merges_entities_and_milestones_ranked():
    ws = _workspace(
        entities=[_entity_result("e1", "Aldea"), _entity_result("e2", "Portal")],
        milestones=[_milestone("m1", "Alianza de Reinos"), _milestone("m2", "Gran Batalla")],
    )
    items = ws._unified_search("al")
    kinds = {it["kind"] for it in items}
    assert kinds == {"graph", "milestone"}  # aparecen ambos tipos
    # BETA-MULTIAGENT2-FIX-04: el orden se AGRUPA POR CLASE (entidades y ramas >
    # hitos > relaciones), así que 'Alianza de Reinos' ya no se cuela entre las
    # dos entidades por empezar por el prefijo. La intención original —prefijo
    # primero— sobrevive DENTRO de cada clase.
    assert [it["title"] for it in items] == ["Aldea", "Portal", "Alianza de Reinos", "Gran Batalla"]
    graficos = [it for it in items if it["kind"] == "graph"]
    hitos = [it for it in items if it["kind"] == "milestone"]
    assert graficos[0]["title"].lower().startswith("al")  # prefijo primero entre entidades
    assert hitos[0]["title"].lower().startswith("al")  # …y entre hitos
    assert items.index(graficos[-1]) < items.index(hitos[0])  # ninguna clase se entremezcla


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_unified_search_empty_query_returns_nothing():
    ws = _workspace([_entity_result("e1", "Aldea")], [_milestone("m1", "Alianza")])
    assert ws._unified_search("   ") == []


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_navigate_to_entity_focuses_in_graph():
    ws = _workspace([_entity_result("e1", "Aldea")], [])
    item = ws._unified_search("aldea")[0]
    assert ws._navigate_search_item(item) is True
    assert ws.graph.focused == [("node", "e1")]
    assert ws._view_switches == []  # ya estaba en concéntrica


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_navigate_to_milestone_switches_to_chronology():
    ws = _workspace([], [_milestone("m1", "Alianza de Reinos")])
    item = ws._unified_search("alianza")[0]
    assert item["kind"] == "milestone"
    assert ws._navigate_search_item(item) is True
    assert ws._view_switches == ["chrono"]  # cambió de vista
    assert ws.chrono.centered == ["m1"]  # centrado síncrono en el hito


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_milestone_recenters_after_view_settles():
    # BETA1-L02c: tras cambiar a la cronología (viewport aún sin tamaño final), se
    # RE-centra diferido en el hito cuando el layout ya está hecho.
    ws = _workspace([], [_milestone("m1", "Alianza de Reinos")])
    item = ws._unified_search("alianza")[0]
    ws._navigate_search_item(item)
    QApplication.processEvents()  # dispara el singleShot del re-centrado
    assert ws.chrono.centered == ["m1", "m1"]  # síncrono + diferido


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_milestone_already_in_chrono_centers_without_reswitch():
    # Si ya estamos en la cronología, centra sin re-cambiar de vista ni diferir.
    ws = _workspace([], [_milestone("m1", "Alianza")], active_view="chrono")
    item = ws._unified_search("alianza")[0]
    assert ws._navigate_search_item(item) is True
    assert ws._view_switches == []  # no recambia de vista
    QApplication.processEvents()
    assert ws.chrono.centered == ["m1"]  # solo el síncrono (sin diferido)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_navigate_to_entity_from_chrono_switches_back():
    ws = _workspace([_entity_result("e1", "Aldea")], [], active_view="chrono")
    item = ws._unified_search("aldea")[0]
    assert ws._navigate_search_item(item) is True
    assert ws._view_switches == ["concentric"]  # vuelve al grafo
    assert ws.graph.focused == [("node", "e1")]


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_typing_does_not_navigate_immediately_debounced():
    # BETA1-L02c: teclear NO navega de inmediato (debounce); solo deja pendiente la
    # mejor coincidencia. Así se puede escribir seguido sin perder el foco.
    ws = _workspace([_entity_result("e1", "Aldea")], [])
    ws._on_search_overlay_text("aldea")
    assert ws.graph.focused == []  # aún NO ha navegado
    assert ws._search_pending_item is not None
    assert ws._search_pending_item["id"] == "e1"


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_fire_search_nav_navigates_to_pending():
    # BETA1-L02c: al vencer el debounce, _fire_search_nav salta a la pendiente.
    ws = _workspace([_entity_result("e1", "Aldea")], [])
    ws._on_search_overlay_text("aldea")
    ws._fire_search_nav()
    assert ws.graph.focused == [("node", "e1")]


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_empty_query_clears_pending():
    ws = _workspace([_entity_result("e1", "Aldea")], [])
    ws._on_search_overlay_text("aldea")
    ws._on_search_overlay_text("")  # se borra el texto
    assert ws._search_pending_item is None
