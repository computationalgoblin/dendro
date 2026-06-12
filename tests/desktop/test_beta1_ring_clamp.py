"""BETA1-C03: constraints de anillos, geometría dinámica e invariantes.

Mayoría sobre los módulos puros (sin Qt); los casos de integración usan el
bridge del canvas.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from packages.ui.graph_physics import (
    UNCLASSIFIED_RING_ID,
    Body,
    ConcentricInvariantChecker,
    PhysicsEngine,
    RingBand,
    Spring,
    resolve_effective_ring_id,
)

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _EdgeView, _NodeView


# ── resolve_effective_ring_id ─────────────────────────────────────────────

def test_effective_ring_explicit_wins():
    assert resolve_effective_ring_id(
        "hoja", explicit_ring_ids={"hoja": "politica"}, membership={"hoja": "rama"},
    ) == "politica"


def test_effective_ring_inherits_from_tree():
    assert resolve_effective_ring_id(
        "hoja", explicit_ring_ids={"rama": "cultura"}, membership={"hoja": "rama"},
    ) == "cultura"


def test_effective_ring_inherits_through_nested_trees():
    assert resolve_effective_ring_id(
        "hoja",
        explicit_ring_ids={"abuela": "metafisica"},
        membership={"hoja": "rama", "rama": "abuela"},
    ) == "metafisica"


def test_effective_ring_unclassified_when_nothing():
    assert resolve_effective_ring_id(
        "suelta", explicit_ring_ids={}, membership={},
    ) == UNCLASSIFIED_RING_ID


def test_effective_ring_survives_membership_cycle():
    # Defensivo: un ciclo de contención jamás debe colgar la resolución
    assert resolve_effective_ring_id(
        "a", explicit_ring_ids={}, membership={"a": "b", "b": "a"},
    ) == UNCLASSIFIED_RING_ID


# ── Clamp de banda en el motor ────────────────────────────────────────────

def band_body(x: float, y: float, inner: float, outer: float, **kw) -> Body:
    return Body("n", x, y, target_radius=(inner + outer) / 2, band_inner=inner, band_outer=outer, **kw)


def radial(body: Body) -> float:
    return math.hypot(body.x, body.y)


def test_node_in_ring_never_leaves_corona_despite_spring():
    """Caso crítico: un muelle fuerte hacia fuera no expulsa al cuerpo."""
    engine = PhysicsEngine(repulsion=0.0)
    inside = band_body(300.0, 0.0, 250.0, 400.0)
    puller = Body("far", 3000.0, 0.0, pinned=True)
    engine.set_world([inside, puller], [Spring("n", "far", ideal_length=50.0, stiffness=0.2)])
    for _ in range(300):
        engine.step()
    assert 250.0 <= radial(engine.bodies["n"]) <= 400.0


def test_external_node_does_not_fall_to_center():
    engine = PhysicsEngine(repulsion=0.0, center_strength=0.0)
    outer_node = band_body(30.0, 0.0, 600.0, 800.0)  # nace cerca del centro
    engine.set_world([outer_node], [])
    for _ in range(300):
        engine.step()
    assert radial(engine.bodies["n"]) >= 600.0  # subió a su corona


def test_inter_ring_spring_does_not_collapse_rings():
    engine = PhysicsEngine(repulsion=0.0)
    a = Body("a", 150.0, 0.0, target_radius=150.0, band_inner=100.0, band_outer=200.0)
    b = Body("b", 700.0, 0.0, target_radius=700.0, band_inner=600.0, band_outer=800.0)
    engine.set_world([a, b], [Spring("a", "b", ideal_length=50.0, stiffness=0.2, strength_factor=0.3)])
    for _ in range(300):
        engine.step()
    assert 100.0 <= radial(engine.bodies["a"]) <= 200.0
    assert 600.0 <= radial(engine.bodies["b"]) <= 800.0


def test_clamp_does_not_jitter_forever():
    """El clamp amortigua la velocidad radial: la energía debe converger."""
    engine = PhysicsEngine(repulsion=0.0)
    inside = band_body(300.0, 0.0, 250.0, 400.0)
    puller = Body("far", 3000.0, 0.0, pinned=True)
    engine.set_world([inside, puller], [Spring("n", "far", ideal_length=50.0, stiffness=0.2)])
    energies = [engine.step() for _ in range(500)]
    assert energies[-1] < 1.0  # sin vibración infinita contra la frontera


def test_clamp_never_produces_nan():
    engine = PhysicsEngine()
    a = band_body(0.0, 0.0, 100.0, 200.0)  # nace en el centro exacto
    engine.set_world([a], [])
    for _ in range(100):
        engine.step()
    body = engine.bodies["n"]
    assert math.isfinite(body.x) and math.isfinite(body.y)
    assert 100.0 <= radial(body) <= 200.0


# ── Invariantes ───────────────────────────────────────────────────────────

def test_invariant_checker_detects_out_of_band_and_overlap():
    checker = ConcentricInvariantChecker(
        bands={
            "a": RingBand("a", 42.0, 200.0),
            "b": RingBand("b", 180.0, 400.0),  # solapa con 'a'
        },
        assignments={"n1": "a", "n2": "a", "n3": ""},
    )
    bodies = {
        "n1": Body("n1", 100.0, 0.0),          # dentro de 'a'
        "n2": Body("n2", 1000.0, 0.0),         # fuera de 'a'
        "n3": Body("n3", float("nan"), 0.0),   # NaN
    }
    kinds = {v.kind for v in checker.check(bodies)}
    assert "overlapping_bands" in kinds
    assert "out_of_band" in kinds
    assert "nan_position" in kinds


def test_invariant_checker_clean_world_passes():
    checker = ConcentricInvariantChecker(
        bands={"a": RingBand("a", 42.0, 200.0), "b": RingBand("b", 240.0, 400.0)},
        assignments={"n1": "a", "n2": "b"},
    )
    bodies = {"n1": Body("n1", 100.0, 0.0), "n2": Body("n2", 0.0, 300.0)}
    assert checker.check(bodies) == []


# ── Integración con el canvas ─────────────────────────────────────────────

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _layer(layer_id, name, rank):
    return SimpleNamespace(id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0)


def _node(entity_id, name, layer_id=""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id, name=name, kind="concepto", subtitle="",
        canon="canonico", visibility="publico", layer_id=layer_id,
    )


@pytest_qt
def test_unclassified_body_goes_to_outer_band_not_center(qapp):
    view = GraphCanvasView()
    layers = [_layer("mundo", "Mundo", 1)]
    view.set_graph(
        [_node("a", "A", "mundo"), _node("suelta", "Suelta")],
        [], layout_mode="concentric_rings", layers=layers,
    )
    view.set_physics_enabled(True)
    bodies = view._physics_engine.bodies
    assert bodies["suelta"].target_radius is not None
    assert bodies["suelta"].target_radius > bodies["a"].target_radius  # exterior


@pytest_qt
def test_canvas_bands_have_no_overlap_and_survive_layout_roundtrip(qapp):
    view = GraphCanvasView()
    layers = [_layer(f"l{i}", f"Capa {i}", i) for i in range(1, 6)]
    nodes = [_node(f"n{i}", f"N{i}", f"l{i}") for i in range(1, 6)]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    view.set_graph(nodes, [], layout_mode="free", layers=layers)
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    bands = {
        ring.ring_id: RingBand(ring.ring_id, ring.inner_radius, ring.outer_radius)
        for ring in view._ring_visuals
    }
    checker = ConcentricInvariantChecker(bands=bands, assignments={})
    geometry_violations = [v for v in checker.check({}) if v.kind in {"overlapping_bands", "degenerate_band"}]
    assert geometry_violations == []


@pytest_qt
def test_more_content_expands_ring(qapp):
    layers = [_layer("mundo", "Mundo", 1)]
    small = GraphCanvasView()
    small.set_graph([_node("a", "A", "mundo")], [], layout_mode="concentric_rings", layers=layers)
    big = GraphCanvasView()
    big.set_graph(
        [_node(f"n{i}", f"N{i}", "mundo") for i in range(10)],
        [], layout_mode="concentric_rings", layers=layers,
    )
    outer_small = next(r for r in small._ring_visuals if r.ring_id == "mundo").outer_radius
    outer_big = next(r for r in big._ring_visuals if r.ring_id == "mundo").outer_radius
    assert outer_big > outer_small
