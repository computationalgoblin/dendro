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

    # ── carga ────────────────────────────────────────────────────────────

    def set_world(self, bodies: list[Body], springs: list[Spring]):
        self.bodies = {body.body_id: body for body in bodies}
        # Solo muelles cuyos dos extremos existen y no son el mismo cuerpo
        self.springs = [
            spring for spring in springs
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
                angle = (index * 2.399963)  # ángulo dorado: sin simetrías
                body.vx += math.cos(angle) * 0.8
                body.vy += math.sin(angle) * 0.8

    # ── simulación ───────────────────────────────────────────────────────

    def step(self, dt: float = 1.0) -> float:
        """Un paso de simulación. Devuelve la energía cinética total."""
        bodies = [b for b in self.bodies.values()]
        forces: dict[str, list[float]] = {b.body_id: [0.0, 0.0] for b in bodies}

        # 1. Repulsión entre pares (O(n²); presupuesto C05: ≤50 cuerpos)
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                a, b = bodies[i], bodies[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist_sq = dx * dx + dy * dy
                min_sep = a.radius + b.radius
                if dist_sq < 1e-6:
                    # Coincidentes: separar de forma determinista
                    dx, dy, dist_sq = 1.0, 0.5, 1.25
                dist = math.sqrt(dist_sq)
                # Repulsión 1/d², reforzada si se solapan
                magnitude = self.repulsion / dist_sq
                if dist < min_sep:
                    magnitude += (min_sep - dist) * 2.0
                fx = (dx / dist) * magnitude
                fy = (dy / dist) * magnitude
                forces[a.body_id][0] -= fx
                forces[a.body_id][1] -= fy
                forces[b.body_id][0] += fx
                forces[b.body_id][1] += fy

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
        #    después y con rigidez mayor que los muelles)
        for body in bodies:
            if body.target_radius is None:
                continue
            dist = math.hypot(body.x, body.y)
            if dist < 1e-6:
                # En el centro exacto: empujar hacia fuera en dirección fija
                direction_x, direction_y = 1.0, 0.0
                dist = 1e-6
            else:
                direction_x, direction_y = body.x / dist, body.y / dist
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

    def is_settled(self) -> bool:
        """True si la energía actual está por debajo del umbral de reposo."""
        energy = sum(
            0.5 * b.mass * (b.vx * b.vx + b.vy * b.vy)
            for b in self.bodies.values()
            if not b.pinned
        )
        return energy < self.min_energy
