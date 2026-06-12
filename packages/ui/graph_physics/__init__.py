"""BETA1 Fase C — física visual mínima y pura (sin Qt).

Contrato: docs/architecture/C01_physics_contract.md.
La física es una capa estética subordinada a los anillos; nunca muta canon
ni layout mode. Solo se simulan cuerpos top-level.
"""
from packages.ui.graph_physics.engine import Body, PhysicsEngine, Spring
from packages.ui.graph_physics.invariants import ConcentricInvariantChecker, InvariantViolation
from packages.ui.graph_physics.rings import (
    UNCLASSIFIED_RING_ID,
    RingBand,
    clamp_to_band,
    resolve_effective_ring_id,
)

__all__ = [
    "Body",
    "ConcentricInvariantChecker",
    "InvariantViolation",
    "PhysicsEngine",
    "RingBand",
    "Spring",
    "UNCLASSIFIED_RING_ID",
    "clamp_to_band",
    "resolve_effective_ring_id",
]
