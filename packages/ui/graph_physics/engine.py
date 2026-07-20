"""BETA1-C02 — motor de física puro para el grafo de Creación.

Diseño (ver docs/architecture/C01_physics_contract.md):

- Sin Qt: opera sobre Bodies con coordenadas de ESCENA. El bridge del canvas
  empaqueta items top-level, llama a step() y aplica posiciones.
- Fuerzas, en orden de prioridad del contrato: resorte radial de anillo
  (target_radius), muelles de relación, repulsión entre cuerpos,
  compactación central (solo layout libre: center_strength > 0), damping.
- Estabilidad primero: damping fuerte, velocidad máxima acotada, auto-stop
  por energía. Nada de NaN/inf: toda división protegida.
- La física NUNCA conoce canon, capas ni layout mode. Solo geometría.

Obsidian-like en sensación, Dendro-like en estructura.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Body:
    """Cuerpo top-level simulable (hoja suelta o rama contenedora entera)."""

    body_id: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    mass: float = 1.0
    radius: float = 62.0  # extensión visual aproximada (para repulsión)
    pinned: bool = False  # drag en curso: la física no lo toca
    # Subordinación a anillos: si está definido, el cuerpo tiende a esta
    # distancia radial del centro (corona de su anillo efectivo).
    target_radius: float | None = None
    # BETA1-C03: banda dura del anillo. Si están definidos, el cuerpo no
    # puede quedar fuera de [band_inner, band_outer] tras un paso (clamp
    # suave de posición con amortiguación radial — invariante de corona).
    band_inner: float | None = None
    band_outer: float | None = None
    # BETA1-C05 (física intrarrama): límites rectangulares (xmin, ymin,
    # xmax, ymax) para cuerpos que viven DENTRO de una rama, en coordenadas
    # locales del contenedor. El clamp mata la componente normal de la
    # velocidad en la pared (sin rebote).
    bounds: tuple[float, float, float, float] | None = None
    # Semilla viva: si está definido, el cuerpo mantiene una velocidad
    # tangencial constante (orbita su corona sin amortiguarse hasta el
    # reposo). El damping decae el resto, pero la tangencial se reinyecta
    # cada paso. None = cuerpo normal (comportamiento sin cambios).
    orbit_speed: float | None = None
    # Deriva del eje: el CENTRO de la órbita migra describiendo un círculo
    # lento de radio orbit_drift (px) a orbit_drift_rate (rad/paso), de modo
    # que el recorrido nunca se repite. orbit_t es el acumulador interno
    # (determinista, sin tiempo real). El clamp de banda sigue centrado en el
    # origen → la semilla nunca abandona su corona.
    orbit_drift: float = 0.0
    orbit_drift_rate: float = 0.0
    orbit_t: float = 0.0
    # Centro de órbita vigente del paso (transitorio, recalculado en step a
    # partir de orbit_t): lo comparten el resorte radial y la reinyección
    # tangencial para que ambos giren en torno al MISMO eje móvil.
    orbit_cx: float = 0.0
    orbit_cy: float = 0.0


@dataclass
class Spring:
    """Relación como muelle entre dos cuerpos top-level."""

    a: str
    b: str
    ideal_length: float = 230.0
    stiffness: float = 0.018
    # Relaciones inter-anillo: fuerza reducida para que el anillo gane
    # (contrato 4.6). El bridge fija <1.0 cuando los anillos difieren.
    strength_factor: float = 1.0


@dataclass
class PhysicsEngine:
    """Simulación conservadora con auto-stop.

    step() devuelve la energía cinética total: el bridge la usa para
    detener el timer cuando el grafo converge (sin vibración infinita).
    """

    repulsion: float = 140_000.0
    damping: float = 0.82
    ring_stiffness: float = 0.055
    center_strength: float = 0.0  # >0 solo en layout libre
    max_speed: float = 26.0
    min_energy: float = 0.35
    bodies: dict[str, Body] = field(default_factory=dict)
    springs: list[Spring] = field(default_factory=list)
    # BETA1-L01: escalabilidad de la repulsión. El cálculo todos-contra-todos
    # es O(n²) — aceptable hasta ~decenas de cuerpos, ruinoso con cientos. Por
    # encima de ``repulsion_bruteforce_max`` se usa una rejilla espacial uniforme
    # (spatial hashing): cada cuerpo solo repele contra los de su celda y las 8
    # vecinas → O(n) en grafos dispersos. La FÓRMULA de fuerza es idéntica; solo
    # cambia el CONJUNTO de pares evaluado (se omite el campo lejano, cuya
    # contribución 1/d² individual es despreciable). ``repulsion_cell`` es el lado
    # de la celda en px: define el alcance (celda + vecinas ≈ 2·celda). Si todos
    # los cuerpos caben en una vecindad, la rejilla coincide EXACTAMENTE con el
    # cálculo bruto (invariante verificado en tests).
    # Medido: cell=260 (≈2× la separación de equilibrio min_sep~124) escala
    # linealmente (~0.04 ms/cuerpo/frame); una celda grande (p.ej. 700) hace que
    # la vecindad 3×3 abarque casi todo el lienzo y degenere a O(n²). Grafos ≤90
    # cuerpos usan el bruto exacto (feel idéntico al histórico).
    repulsion_bruteforce_max: int = 90
    repulsion_cell: float = 260.0

    # ── carga ────────────────────────────────────────────────────────────

    def set_world(self, bodies: list[Body], springs: list[Spring]):
        self.bodies = {body.body_id: body for body in bodies}
        # Solo muelles cuyos dos extremos existen y no son el mismo cuerpo
        self.springs = [
            spring
            for spring in springs
            if spring.a != spring.b and spring.a in self.bodies and spring.b in self.bodies
        ]

    def sync_position(self, body_id: str, x: float, y: float):
        """El usuario (u otra capa) movió un cuerpo: adoptar sin impulso."""
        body = self.bodies.get(body_id)
        if body is not None:
            body.x, body.y = float(x), float(y)
            body.vx = body.vy = 0.0

    def set_pinned(self, body_id: str, pinned: bool):
        body = self.bodies.get(body_id)
        if body is not None:
            body.pinned = bool(pinned)
            if pinned:
                body.vx = body.vy = 0.0

    def reheat(self):
        """Pequeño impulso determinista para reactivar tras auto-stop."""
        for index, body in enumerate(self.bodies.values()):
            if not body.pinned:
                angle = index * 2.399963  # ángulo dorado: sin simetrías
                body.vx += math.cos(angle) * 0.8
                body.vy += math.sin(angle) * 0.8

    def apply_breeze(self, angle: float, strength: float = 0.6):
        """BETA2-PULIDO-07: ráfaga suave direccional — agita los cuerpos vivos
        con variación determinista por índice (no se mecen al unísono). Los
        ``pinned`` (sedientas/secadas del jardín, drags) quedan clavados."""
        for index, body in enumerate(self.bodies.values()):
            if body.pinned:
                continue
            jitter = 0.7 + 0.3 * math.sin(index * 2.399963)
            body.vx += math.cos(angle) * strength * jitter
            body.vy += math.sin(angle) * strength * jitter

    # ── simulación ───────────────────────────────────────────────────────

    def step(self, dt: float = 1.0) -> float:
        """Un paso de simulación. Devuelve la energía cinética total."""
        bodies = [b for b in self.bodies.values()]
        forces: dict[str, list[float]] = {b.body_id: [0.0, 0.0] for b in bodies}

        # 0. Eje de órbita del paso (deriva): el centro migra lento describiendo
        #    un círculo de radio orbit_drift. Se calcula una sola vez por paso y
        #    lo usan el resorte radial (sección 3) y la tangente (sección 5).
        for body in bodies:
            if body.orbit_speed is not None:
                body.orbit_t += body.orbit_drift_rate
                body.orbit_cx = body.orbit_drift * math.cos(body.orbit_t)
                body.orbit_cy = body.orbit_drift * math.sin(body.orbit_t)

        # 1. Repulsión entre pares. BETA1-L01: bruto O(n²) en grafos pequeños
        #    (idéntico al comportamiento histórico), rejilla espacial O(n) por
        #    encima del umbral. Ambos caminos usan _apply_pair_repulsion.
        if len(bodies) <= self.repulsion_bruteforce_max:
            for i in range(len(bodies)):
                for j in range(i + 1, len(bodies)):
                    self._apply_pair_repulsion(bodies[i], bodies[j], forces)
        else:
            self._apply_grid_repulsion(bodies, forces)

        # 2. Muelles de relación
        for spring in self.springs:
            a = self.bodies[spring.a]
            b = self.bodies[spring.b]
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.hypot(dx, dy) or 1e-6
            stretch = dist - spring.ideal_length
            magnitude = spring.stiffness * spring.strength_factor * stretch
            fx = (dx / dist) * magnitude
            fy = (dy / dist) * magnitude
            forces[spring.a][0] += fx
            forces[spring.a][1] += fy
            forces[spring.b][0] -= fx
            forces[spring.b][1] -= fy

        # 3. Resorte radial de anillo (gana por construcción: se aplica
        #    después y con rigidez mayor que los muelles). Para semillas vivas
        #    el resorte tira hacia el eje MÓVIL (deriva), no hacia el origen, de
        #    modo que la órbita migra; el clamp de banda (sección 5, centrado en
        #    el origen) sigue garantizando que no abandona la corona.
        for body in bodies:
            if body.target_radius is None:
                continue
            ox = body.orbit_cx if body.orbit_speed is not None else 0.0
            oy = body.orbit_cy if body.orbit_speed is not None else 0.0
            rx, ry = body.x - ox, body.y - oy
            dist = math.hypot(rx, ry)
            if dist < 1e-6:
                # En el centro exacto: empujar hacia fuera en dirección fija
                direction_x, direction_y = 1.0, 0.0
                dist = 1e-6
            else:
                direction_x, direction_y = rx / dist, ry / dist
            deviation = body.target_radius - dist
            magnitude = self.ring_stiffness * deviation * body.mass
            forces[body.body_id][0] += direction_x * magnitude
            forces[body.body_id][1] += direction_y * magnitude

        # 4. Compactación central (solo libre; en concéntrico debe ser 0)
        if self.center_strength > 0.0:
            for body in bodies:
                forces[body.body_id][0] -= body.x * self.center_strength
                forces[body.body_id][1] -= body.y * self.center_strength

        # 5. Integración con damping y velocidad acotada
        energy = 0.0
        for body in bodies:
            if body.pinned:
                continue
            fx, fy = forces[body.body_id]
            body.vx = (body.vx + (fx / body.mass) * dt) * self.damping
            body.vy = (body.vy + (fy / body.mass) * dt) * self.damping
            # Semilla viva: reinyectar la componente tangencial para que
            # orbite su corona sin asentarse (el damping ya decayó la previa).
            # La repulsión sigue empujando a los vecinos (grafo "vivo").
            if body.orbit_speed is not None:
                # Tangente en torno al eje móvil del paso (sección 0): recorrido
                # irregular que no se repite, en sintonía con el resorte radial.
                cx, cy = body.orbit_cx, body.orbit_cy
                rx, ry = body.x - cx, body.y - cy
                d = math.hypot(rx, ry)
                if d < 1e-6:
                    # Sin radial definida: arrancar en target_radius (o band)
                    r0 = body.target_radius
                    if r0 is None and body.band_inner is not None and body.band_outer is not None:
                        r0 = (body.band_inner + body.band_outer) / 2.0
                    if r0:
                        body.x, body.y = float(r0) + cx, cy
                        body.vx, body.vy = 0.0, body.orbit_speed
                else:
                    tx, ty = -ry / d, rx / d
                    v_tan = body.vx * tx + body.vy * ty
                    corr = body.orbit_speed - v_tan
                    body.vx += corr * tx
                    body.vy += corr * ty
            speed = math.hypot(body.vx, body.vy)
            if speed > self.max_speed:
                scale = self.max_speed / speed
                body.vx *= scale
                body.vy *= scale
            body.x += body.vx * dt
            body.y += body.vy * dt
            if not (math.isfinite(body.x) and math.isfinite(body.y)):
                # Invariante: jamás propagar NaN/inf al canvas
                body.x, body.y = 0.0, 0.0
                body.vx = body.vy = 0.0
            # BETA1-C03: clamp de banda — la corona radial GANA a cualquier
            # muelle (prioridad 1 del contrato). Reproyección al borde más
            # cercano + amortiguación de la velocidad radial saliente, para
            # que el muelle no produzca jitter contra la frontera.
            if body.band_inner is not None and body.band_outer is not None:
                dist = math.hypot(body.x, body.y)
                inner = max(0.0, body.band_inner)
                outer = max(inner, body.band_outer)
                if dist < 1e-9:
                    body.x, body.y = (inner + outer) / 2.0, 0.0
                    body.vx = body.vy = 0.0
                elif dist < inner or dist > outer:
                    bound = inner if dist < inner else outer
                    scale = bound / dist
                    body.x *= scale
                    body.y *= scale
                    # quitar la componente radial de la velocidad (la
                    # tangencial se conserva: el cuerpo puede deslizarse
                    # por la corona sin rebotar)
                    nx, ny = body.x / bound, body.y / bound
                    radial = body.vx * nx + body.vy * ny
                    body.vx -= radial * nx
                    body.vy -= radial * ny
            # BETA1-C05: clamp rectangular (interior de rama)
            if body.bounds is not None:
                xmin, ymin, xmax, ymax = body.bounds
                if xmin > xmax:
                    xmin = xmax = (xmin + xmax) / 2.0
                if ymin > ymax:
                    ymin = ymax = (ymin + ymax) / 2.0
                if body.x < xmin:
                    body.x, body.vx = xmin, max(0.0, body.vx)
                elif body.x > xmax:
                    body.x, body.vx = xmax, min(0.0, body.vx)
                if body.y < ymin:
                    body.y, body.vy = ymin, max(0.0, body.vy)
                elif body.y > ymax:
                    body.y, body.vy = ymax, min(0.0, body.vy)
            energy += 0.5 * body.mass * (body.vx * body.vx + body.vy * body.vy)
        return energy

    # ── repulsión: pares y rejilla espacial (BETA1-L01) ──────────────────

    def _apply_pair_repulsion(
        self, a: Body, b: Body, forces: dict[str, list[float]]
    ) -> None:
        """Repulsión entre dos cuerpos (1/d², reforzada si se solapan).

        Fórmula histórica intacta; extraída para que el camino bruto y el de
        rejilla compartan exactamente el mismo cálculo de fuerza."""
        dx = b.x - a.x
        dy = b.y - a.y
        dist_sq = dx * dx + dy * dy
        min_sep = a.radius + b.radius
        if dist_sq < 1e-6:
            # Coincidentes: separar de forma determinista
            dx, dy, dist_sq = 1.0, 0.5, 1.25
        dist = math.sqrt(dist_sq)
        magnitude = self.repulsion / dist_sq
        if dist < min_sep:
            magnitude += (min_sep - dist) * 2.0
        fx = (dx / dist) * magnitude
        fy = (dy / dist) * magnitude
        forces[a.body_id][0] -= fx
        forces[a.body_id][1] -= fy
        forces[b.body_id][0] += fx
        forces[b.body_id][1] += fy

    def _apply_grid_repulsion(
        self, bodies: list[Body], forces: dict[str, list[float]]
    ) -> None:
        """Repulsión O(n) por rejilla espacial uniforme (spatial hashing).

        Cada cuerpo se asigna a una celda de lado ``repulsion_cell``; solo se
        evalúan pares dentro de la misma celda o de las 8 vecinas. El orden de
        índice global deduplica cada par no ordenado (se aplica una sola vez).
        El campo lejano (más allá de ~2·celda) se omite: su contribución 1/d²
        individual es despreciable y la suma se compensa con el clamp y el
        damping. Determinista: sin aleatoriedad ni dependencia del tiempo."""
        cell = self.repulsion_cell if self.repulsion_cell > 1e-6 else 700.0
        grid: dict[tuple[int, int], list[int]] = {}
        cells: list[tuple[int, int]] = []
        for idx, body in enumerate(bodies):
            if math.isfinite(body.x) and math.isfinite(body.y):
                key = (int(body.x // cell), int(body.y // cell))
            else:
                key = (0, 0)
            grid.setdefault(key, []).append(idx)
            cells.append(key)
        neighborhood = (-1, 0, 1)
        for idx, body in enumerate(bodies):
            cx, cy = cells[idx]
            for dx in neighborhood:
                for dy in neighborhood:
                    bucket = grid.get((cx + dx, cy + dy))
                    if not bucket:
                        continue
                    for jdx in bucket:
                        if jdx <= idx:
                            continue  # cada par no ordenado, una sola vez
                        self._apply_pair_repulsion(body, bodies[jdx], forces)

    def is_settled(self) -> bool:
        """True si la energía actual está por debajo del umbral de reposo."""
        energy = sum(
            0.5 * b.mass * (b.vx * b.vx + b.vy * b.vy) for b in self.bodies.values() if not b.pinned
        )
        return energy < self.min_energy

    def has_live_orbiters(self) -> bool:
        """True si hay algún cuerpo orbitando (semilla viva): el bridge no
        debe auto-detener el timer mientras exista uno."""
        return any(b.orbit_speed is not None for b in self.bodies.values())
