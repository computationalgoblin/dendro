"""BETA1-C03 — ConcentricInvariantChecker (puro, para tests y QA).

Detecta violaciones del contrato concéntrico (C01 §4.3, fase C ticket C03).
No corrige nada: solo informa. El bridge/los tests deciden qué hacer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from packages.ui.graph_physics.engine import Body
from packages.ui.graph_physics.rings import RingBand, UNCLASSIFIED_RING_ID


@dataclass
class InvariantViolation:
    kind: str
    subject: str
    detail: str


@dataclass
class ConcentricInvariantChecker:
    """Comprueba cuerpos contra bandas de anillos.

    `assignments` mapea body_id → ring_id efectivo; `bands` mapea
    ring_id → RingBand. `margin` tolera el grosor visual del item.
    """

    bands: dict[str, RingBand] = field(default_factory=dict)
    assignments: dict[str, str] = field(default_factory=dict)
    margin: float = 4.0

    def check(self, bodies: dict[str, Body]) -> list[InvariantViolation]:
        violations: list[InvariantViolation] = []
        violations.extend(self._check_band_geometry())
        for body_id, body in bodies.items():
            if not (math.isfinite(body.x) and math.isfinite(body.y)):
                violations.append(InvariantViolation(
                    "nan_position", body_id, f"posición no finita: ({body.x}, {body.y})"
                ))
                continue
            ring_id = self.assignments.get(body_id, "")
            if not ring_id:
                violations.append(InvariantViolation(
                    "missing_effective_ring", body_id,
                    "cuerpo sin anillo efectivo resuelto",
                ))
                continue
            band = self.bands.get(ring_id)
            if band is None:
                violations.append(InvariantViolation(
                    "unknown_ring", body_id, f"anillo '{ring_id}' sin banda registrada"
                ))
                continue
            dist = math.hypot(body.x, body.y)
            if not band.contains(dist, margin=-self.margin):
                violations.append(InvariantViolation(
                    "out_of_band", body_id,
                    f"r={dist:.1f} fuera de [{band.inner_radius:.1f}, {band.outer_radius:.1f}] "
                    f"(anillo '{ring_id}')",
                ))
        return violations

    def _check_band_geometry(self) -> list[InvariantViolation]:
        violations: list[InvariantViolation] = []
        ordered = sorted(self.bands.values(), key=lambda band: band.inner_radius)
        previous: RingBand | None = None
        for band in ordered:
            if band.outer_radius <= band.inner_radius:
                violations.append(InvariantViolation(
                    "degenerate_band", band.ring_id,
                    f"outer ({band.outer_radius:.1f}) <= inner ({band.inner_radius:.1f})",
                ))
            if band.ring_id != UNCLASSIFIED_RING_ID and band.target_radius <= 0.0:
                violations.append(InvariantViolation(
                    "zero_target_radius", band.ring_id, "target_radius <= 0",
                ))
            if previous is not None and band.inner_radius < previous.outer_radius:
                violations.append(InvariantViolation(
                    "overlapping_bands", band.ring_id,
                    f"inner ({band.inner_radius:.1f}) < outer del anterior "
                    f"({previous.outer_radius:.1f}, '{previous.ring_id}')",
                ))
            previous = band
        return violations
