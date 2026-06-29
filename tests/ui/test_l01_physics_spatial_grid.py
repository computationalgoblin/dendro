"""BETA1-L01 — rejilla espacial de repulsión en PhysicsEngine.

Verifica que el camino de rejilla (O(n)) es EQUIVALENTE al cálculo bruto
(O(n²)) cuando todos los cuerpos caben en una vecindad, y que escala a cientos
de cuerpos sin coste cuadrático. Motor puro (sin Qt)."""

from __future__ import annotations

import math

from packages.ui.graph_physics.engine import Body, PhysicsEngine


def _grid_forces(bodies: list[Body], cell: float) -> dict[str, list[float]]:
    engine = PhysicsEngine(repulsion_cell=cell)
    engine.set_world(bodies, [])
    forces = {b.body_id: [0.0, 0.0] for b in bodies}
    engine._apply_grid_repulsion(list(engine.bodies.values()), forces)
    return forces


def _brute_forces(bodies: list[Body]) -> dict[str, list[float]]:
    engine = PhysicsEngine()
    engine.set_world(bodies, [])
    forces = {b.body_id: [0.0, 0.0] for b in bodies}
    ordered = list(engine.bodies.values())
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            engine._apply_pair_repulsion(ordered[i], ordered[j], forces)
    return forces


def test_grid_equals_bruteforce_when_all_within_one_neighborhood():
    """Invariante clave: si todos los cuerpos caben en celda+vecinas, la rejilla
    evalúa exactamente los mismos pares que el bruto → fuerzas idénticas."""
    bodies = [
        Body("a", 0.0, 0.0),
        Body("b", 120.0, 30.0),
        Body("c", -80.0, 90.0),
        Body("d", 60.0, -110.0),
        Body("e", 200.0, 150.0),
    ]
    cell = 1000.0  # todos los cuerpos en una vecindad de celdas
    grid = _grid_forces(bodies, cell)
    brute = _brute_forces(bodies)
    for bid in grid:
        assert math.isclose(grid[bid][0], brute[bid][0], rel_tol=1e-12, abs_tol=1e-9)
        assert math.isclose(grid[bid][1], brute[bid][1], rel_tol=1e-12, abs_tol=1e-9)


def test_grid_skips_far_field_pairs():
    """Dos cúmulos muy separados (más de 2·celda) no se repelen entre sí en la
    rejilla, pero sí dentro de cada cúmulo (campo cercano preservado)."""
    cell = 300.0
    bodies = [
        Body("a0", 0.0, 0.0),
        Body("a1", 50.0, 0.0),
        Body("z0", 5000.0, 0.0),
        Body("z1", 5050.0, 0.0),
    ]
    grid = _grid_forces(bodies, cell)
    # a0 recibe fuerza (de a1, vecino cercano), pero nada del cúmulo lejano:
    # su empuje es exactamente el de un par a0-a1 aislado.
    pair_only = _brute_forces([Body("a0", 0.0, 0.0), Body("a1", 50.0, 0.0)])
    assert math.isclose(grid["a0"][0], pair_only["a0"][0], rel_tol=1e-12, abs_tol=1e-9)
    assert math.isclose(grid["a0"][1], pair_only["a0"][1], rel_tol=1e-12, abs_tol=1e-9)


def test_step_dispatches_to_grid_above_threshold_and_is_finite():
    """Un grafo grande (cientos de cuerpos) corre step() sin coste cuadrático y
    sin NaN/inf — usa el camino de rejilla por superar el umbral."""
    n = 400
    bodies = []
    for i in range(n):
        angle = i * 2.399963
        r = 300.0 + (i % 50) * 12.0
        bodies.append(Body(f"n{i}", r * math.cos(angle), r * math.sin(angle)))
    engine = PhysicsEngine()
    assert n > engine.repulsion_bruteforce_max  # se ejercita la rejilla
    engine.set_world(bodies, [])
    energy = engine.step()
    assert math.isfinite(energy)
    for body in engine.bodies.values():
        assert math.isfinite(body.x) and math.isfinite(body.y)


def _spread(n: int) -> list[Body]:
    """Grafo asentado: espiral de ángulo dorado → densidad de área uniforme."""
    out = []
    for i in range(n):
        r = 90.0 * math.sqrt(i + 1)
        angle = i * 2.399963
        out.append(Body(f"n{i}", r * math.cos(angle), r * math.sin(angle)))
    return out


def test_grid_pair_count_is_linear_not_quadratic():
    """Garantía O(N) (determinista, sin tiempo): con densidad de equilibrio, los
    pares evaluados crecen ~linealmente con N, no como N². Pinchazo de regresión
    si alguien sube ``repulsion_cell`` y la rejilla deja de podar."""

    def pairs_evaluated(n: int) -> int:
        engine = PhysicsEngine()  # defaults de producción (cell=260)
        engine.set_world(_spread(n), [])
        count = 0
        original = engine._apply_pair_repulsion

        def counting(a, b, forces):
            nonlocal count
            count += 1
            return original(a, b, forces)

        engine._apply_pair_repulsion = counting
        engine._apply_grid_repulsion(list(engine.bodies.values()), {
            bid: [0.0, 0.0] for bid in engine.bodies
        })
        return count

    p1000 = pairs_evaluated(1000)
    p2000 = pairs_evaluated(2000)
    # Cuadrático sería 500k / 2M. Lineal: muy por debajo, y ~2× al doblar N.
    assert p1000 < 1000 * 1000 // 2 // 10  # <10% de los pares O(n²)
    assert p2000 < 2.6 * p1000  # crece ~linealmente (no ~4× como sería O(n²))


def test_grid_pairs_counted_once_symmetric_system():
    """Cada par no ordenado se aplica una sola vez (acción-reacción simétrica):
    la suma total de fuerzas de repulsión es ~0 (sistema cerrado)."""
    bodies = [Body(f"n{i}", (i % 7) * 90.0, (i // 7) * 90.0) for i in range(70)]
    engine = PhysicsEngine(repulsion_bruteforce_max=10, repulsion_cell=200.0)
    engine.set_world(bodies, [])
    forces = {b.body_id: [0.0, 0.0] for b in bodies}
    engine._apply_grid_repulsion(list(engine.bodies.values()), forces)
    sum_x = sum(f[0] for f in forces.values())
    sum_y = sum(f[1] for f in forces.values())
    assert math.isclose(sum_x, 0.0, abs_tol=1e-6)
    assert math.isclose(sum_y, 0.0, abs_tol=1e-6)
