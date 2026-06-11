"""BETA1 Fase C — física visual mínima y pura (sin Qt).

Contrato: docs/architecture/C01_physics_contract.md.
La física es una capa estética subordinada a los anillos; nunca muta canon
ni layout mode. Solo se simulan cuerpos top-level.
"""
from packages.ui.graph_physics.engine import Body, PhysicsEngine, Spring

__all__ = ["Body", "PhysicsEngine", "Spring"]
