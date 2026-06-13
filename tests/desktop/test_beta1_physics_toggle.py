"""BETA1-C02: toggle de física ON/OFF independiente del layout mode.

Parte 1: motor puro (sin Qt). Parte 2: bridge del canvas (flag, timer,
ortogonalidad con layout). Parte 3: contrato estático (sin
"concentric_physics" en código).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.ui.graph_physics import Body, PhysicsEngine, Spring

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _EdgeView, _NodeView


ROOT = Path(__file__).resolve().parents[2]


# ── Motor puro ────────────────────────────────────────────────────────────

def test_spring_pulls_bodies_together():
    engine = PhysicsEngine(repulsion=0.0)
    engine.set_world(
        [Body("a", -400.0, 0.0), Body("b", 400.0, 0.0)],
        [Spring("a", "b", ideal_length=200.0)],
    )
    for _ in range(80):
        engine.step()
    dist = abs(engine.bodies["b"].x - engine.bodies["a"].x)
    assert dist < 800.0  # se acercaron
    assert dist > 50.0   # sin colapsar en un punto


def test_repulsion_separates_overlapping_bodies():
    engine = PhysicsEngine()
    engine.set_world([Body("a", 0.0, 0.0), Body("b", 1.0, 0.0)], [])
    for _ in range(40):
        engine.step()
    dist = abs(engine.bodies["b"].x - engine.bodies["a"].x)
    assert dist > 60.0


def test_damping_converges_to_rest():
    engine = PhysicsEngine()
    engine.set_world(
        [Body("a", -300.0, 0.0), Body("b", 300.0, 0.0)],
        [Spring("a", "b")],
    )
    engine.reheat()
    energies = [engine.step() for _ in range(400)]
    assert energies[-1] < engine.min_energy  # auto-stop alcanzable
    assert engine.is_settled()


def test_pinned_body_never_moves():
    engine = PhysicsEngine()
    engine.set_world(
        [Body("a", 0.0, 0.0, pinned=True), Body("b", 50.0, 0.0)],
        [Spring("a", "b")],
    )
    for _ in range(60):
        engine.step()
    assert engine.bodies["a"].x == 0.0 and engine.bodies["a"].y == 0.0


def test_ring_target_radius_attracts_radially():
    engine = PhysicsEngine(repulsion=0.0)
    engine.set_world([Body("a", 50.0, 0.0, target_radius=400.0)], [])
    for _ in range(200):
        engine.step()
    import math
    dist = math.hypot(engine.bodies["a"].x, engine.bodies["a"].y)
    assert 300.0 < dist < 500.0  # tendió a su corona


def test_step_never_produces_nan():
    engine = PhysicsEngine()
    engine.set_world(
        [Body("a", 0.0, 0.0), Body("b", 0.0, 0.0)],  # coincidentes
        [Spring("a", "b", ideal_length=0.0)],
    )
    import math
    for _ in range(50):
        engine.step()
    for body in engine.bodies.values():
        assert math.isfinite(body.x) and math.isfinite(body.y)


# ── Bridge del canvas ─────────────────────────────────────────────────────

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _node(entity_id: str, name: str, layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind="concepto",
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def _edge(relation_id: str, a: str, b: str, kind: str = "deriva_de"):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=a,
        target_id=b,
        kind=kind,
        label=kind.replace("_", " "),
    )


@pytest_qt
def test_physics_always_on_by_default_and_flag_never_touches_layout(qapp):
    """Decisión de producto (C05): física SIEMPRE ON — sin toggle de
    usuario. El flag interno sigue existiendo para tests/fallback."""
    view = GraphCanvasView()
    view.set_graph([_node("a", "A"), _node("b", "B")], [_edge("r", "a", "b")])
    layout_before = view._layout_mode_active

    # ON por defecto, simulación en marcha tras el primer set_graph
    assert view.physics_enabled() is True
    assert view._physics_timer.isActive() is True
    assert view._layout_mode_active == layout_before

    # el flag interno sigue siendo ortogonal al layout
    view.set_physics_enabled(False)
    assert view.physics_enabled() is False
    assert view._physics_timer.isActive() is False
    assert view._layout_mode_active == layout_before

    view.set_physics_enabled(True)
    assert view._physics_timer.isActive() is True
    assert view._layout_mode_active == layout_before


@pytest_qt
def test_any_rebuild_reheats_physics(qapp):
    """Decisión de producto (C05): cualquier acción (CRUD → refresh →
    set_graph) re-activa la acomodación aunque hubiera convergido."""
    view = GraphCanvasView()
    view.set_graph([_node("a", "A")], [])
    view._physics_timer.stop()  # simula auto-stop por convergencia
    view.set_graph([_node("a", "A"), _node("b", "B")], [_edge("r", "a", "b")])
    assert view._physics_timer.isActive() is True  # despertó sola
    assert "b" in view._physics_engine.bodies


@pytest_qt
def test_intra_branch_local_physics(qapp):
    """Decisión de producto (C05): física TAMBIÉN dentro de las ramas — los
    hijos se acomodan en coordenadas locales, sin salir del rectángulo."""
    view = GraphCanvasView()
    layers = [SimpleNamespace(id="mundo", name="Mundo", metadata={"causal_rank": "1"}, is_visible=True, order=0)]
    rama = _NodeView(
        entity=SimpleNamespace(id="rama", name="Rama", layer_ids=["mundo"]),
        entity_id="rama", name="Rama", kind="contenedor", subtitle="",
        canon="canonico", visibility="publico", layer_id="mundo",
    )
    nodes = [rama, _node("h1", "H1"), _node("h2", "H2"), _node("h3", "H3")]
    edges = [
        _edge("c1", "rama", "h1", kind="contiene"),
        _edge("c2", "rama", "h2", kind="contiene"),
        _edge("c3", "rama", "h3", kind="contiene"),
    ]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    assert "rama" in view._physics_local  # motor local creado
    local = view._physics_local["rama"]
    assert len(local.bodies) == 3
    tree = view._trees["rama"]
    before = {c.node.entity_id: (c.pos().x(), c.pos().y()) for c in tree._child_nodes}
    for _ in range(12):
        view._physics_tick()
    after = {c.node.entity_id: (c.pos().x(), c.pos().y()) for c in tree._child_nodes}
    assert before != after  # los hijos se acomodan
    # y ninguno se sale del rectángulo de la rama
    rect = tree.rect()
    for child in tree._child_nodes:
        assert rect.left() - 1 <= child.pos().x() <= rect.right() + 1
        assert rect.top() - 1 <= child.pos().y() <= rect.bottom() + 1


@pytest_qt
def test_physics_tick_moves_nodes(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "A"), _node("b", "B"), _node("c", "C")], [_edge("r", "a", "b")])
    view.set_physics_enabled(True)
    before = {eid: (item.scenePos().x(), item.scenePos().y()) for eid, item in view._nodes.items()}
    for _ in range(10):
        view._physics_tick()
    moved = any(
        (item.scenePos().x(), item.scenePos().y()) != before[eid]
        for eid, item in view._nodes.items()
    )
    assert moved is True


@pytest_qt
def test_layout_change_preserves_physics_flag(qapp):
    view = GraphCanvasView()
    layers = [SimpleNamespace(id="mundo", name="Mundo", metadata={"causal_rank": "1"}, is_visible=True, order=0)]
    view.set_graph([_node("a", "A", "mundo")], [], layout_mode="concentric_rings", layers=layers)
    view.set_physics_enabled(True)
    view.set_graph([_node("a", "A", "mundo")], [], layout_mode="free", layers=layers)
    assert view.physics_enabled() is True  # cambiar layout no toca física
    assert view._layout_mode_active == "free"  # física no toca layout
    view.set_graph([_node("a", "A", "mundo")], [], layout_mode="concentric_rings", layers=layers)
    assert view.physics_enabled() is True
    assert view._layout_mode_active == "concentric_rings"


@pytest_qt
def test_concentric_bodies_get_ring_targets(qapp):
    view = GraphCanvasView()
    layers = [
        SimpleNamespace(id="mundo", name="Mundo", metadata={"causal_rank": "1"}, is_visible=True, order=0),
        SimpleNamespace(id="gente", name="Gente", metadata={"causal_rank": "2"}, is_visible=True, order=0),
    ]
    view.set_graph(
        [_node("a", "A", "mundo"), _node("b", "B", "gente")],
        [_edge("r", "a", "b")],
        layout_mode="concentric_rings",
        layers=layers,
    )
    view.set_physics_enabled(True)
    bodies = view._physics_engine.bodies
    assert bodies["a"].target_radius is not None  # subordinado a su anillo
    assert bodies["b"].target_radius is not None
    assert bodies["a"].target_radius < bodies["b"].target_radius  # anillo interior < exterior
    # muelle inter-anillo: fuerza reducida (contrato C01 §4.6)
    spring = view._physics_engine.springs[0]
    assert spring.strength_factor < 1.0
    # compactación central nula en concéntrico
    assert view._physics_engine.center_strength == 0.0


@pytest_qt
def test_physics_stays_live_during_drag(qapp):
    """Decisión de producto (C05): el grafo reacciona EN VIVO al arrastre —
    el item en mano va pinned (lo lleva el usuario) y el resto se acomoda."""
    view = GraphCanvasView()
    view.set_graph([_node("a", "A"), _node("b", "B")], [_edge("r", "a", "b")])
    item_a = view._nodes["a"]
    view._moving_item = item_a  # drag en curso
    # el usuario lo lleva lejos: el muelle debe arrastrar a 'b' tras él
    item_a.setPos(item_a.pos().x() + 1200, item_a.pos().y())
    a_after_user = (item_a.scenePos().x(), item_a.scenePos().y())
    b_before = view._nodes["b"].scenePos().x()
    for _ in range(20):
        view._physics_tick()
    # el arrastrado NO lo mueve la física (pinned, lo lleva el usuario)
    assert (item_a.scenePos().x(), item_a.scenePos().y()) == a_after_user
    assert view._physics_engine.bodies["a"].pinned is True
    # pero el resto reacciona en vivo
    assert view._nodes["b"].scenePos().x() != b_before
    view._moving_item = None
    view._physics_reheat()
    assert all(b.pinned is False for b in view._physics_engine.bodies.values())


@pytest_qt
def test_tick_fully_paused_in_pan_and_relation_modes(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "A"), _node("b", "B")], [_edge("r", "a", "b")])
    before = view._nodes["b"].scenePos().x()
    view._space_pan_active = True
    view._physics_tick()
    assert view._nodes["b"].scenePos().x() == before  # paneo: pausa total
    view._space_pan_active = False


# ── Rendimiento (C05) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("body_count", [10, 25, 50])
def test_engine_performance_budget(body_count):
    """C05: el motor puro debe ser barato — 120 pasos (≈4s de simulación a
    30 Hz) muy por debajo del presupuesto de frame. Umbral generoso para
    máquinas lentas: si esto falla, la física es inviable en ese equipo."""
    import random
    import time

    rng = random.Random(42)
    # Corpus realista: los cuerpos se reparten en 3 coronas con espacio
    # suficiente (forzar 50 cuerpos de radio 62 en una sola corona es
    # físicamente imposible — churn permanente; en el canvas real los
    # anillos se EXPANDEN vía _refresh_ring_spans).
    coronas = [(250.0, 400.0, 550.0), (650.0, 800.0, 950.0), (1050.0, 1200.0, 1350.0)]
    bodies = []
    for i in range(body_count):
        inner, target, outer = coronas[i % 3]
        bodies.append(Body(
            f"n{i}", rng.uniform(-800, 800), rng.uniform(-800, 800),
            target_radius=target, band_inner=inner, band_outer=outer,
        ))
    springs = [
        Spring(f"n{i}", f"n{(i * 7 + 3) % body_count}")
        for i in range(min(body_count, 30))
    ]
    engine = PhysicsEngine()
    engine.set_world(bodies, springs)
    start = time.perf_counter()
    for _ in range(120):
        engine.step()
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"{body_count} cuerpos: {elapsed:.2f}s para 120 pasos"
    # y converge: sin vibración infinita
    for _ in range(600):
        if engine.step() < engine.min_energy:
            break
    assert engine.is_settled() or engine.step() < 5.0


# ── Contrato estático ─────────────────────────────────────────────────────

def test_no_concentric_physics_layout_mode_in_code():
    """Prohibido el pseudo-layout 'concentric_physics' (contrato C01)."""
    for relative in (
        "hosts/DesktopHostPySide/widgets/graph_canvas.py",
        "hosts/DesktopHostPySide/views/workspaces.py",
        "packages/ui/graph_physics/engine.py",
        "packages/ui/graph_physics/__init__.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "concentric_physics" not in text, relative
