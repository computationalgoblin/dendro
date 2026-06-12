"""BETA1-C03 — anillos como campos espaciales (puro, sin Qt).

Centraliza la resolución del anillo efectivo de cada item y el modelo de
banda radial. Contrato: docs/architecture/C01_physics_contract.md §4.2-4.3.
"""
from __future__ import annotations

from dataclasses import dataclass

UNCLASSIFIED_RING_ID = "__unclassified__"


@dataclass(frozen=True)
class RingBand:
    """Zona radial de un anillo: [inner, outer], con radio objetivo."""

    ring_id: str
    inner_radius: float
    outer_radius: float

    @property
    def target_radius(self) -> float:
        return (self.inner_radius + self.outer_radius) / 2.0

    def contains(self, radial_distance: float, *, margin: float = 0.0) -> bool:
        return (self.inner_radius + margin) <= radial_distance <= (self.outer_radius - margin)


def resolve_effective_ring_id(
    entity_id: str,
    *,
    explicit_ring_ids: dict[str, str],
    membership: dict[str, str],
    is_tree: set[str] | frozenset[str] = frozenset(),
    _visited: set[str] | None = None,
) -> str:
    """Anillo efectivo de un item (contrato C01 §4.2).

    - Hoja/rama con anillo explícito → el suyo.
    - Hoja sin anillo dentro de una rama → hereda el efectivo de la rama.
    - Sin nada → "__unclassified__" (banda exterior).

    `explicit_ring_ids` mapea entity_id → ring_id REAL (no incluye la
    asignación sintética a "Sin clasificar"); `membership` mapea
    entity_id → rama contenedora ('contiene').
    """
    if _visited is None:
        _visited = set()
    if entity_id in _visited:
        return UNCLASSIFIED_RING_ID  # ciclo defensivo: nunca recursión infinita
    _visited.add(entity_id)

    explicit = explicit_ring_ids.get(entity_id, "")
    if explicit and explicit != UNCLASSIFIED_RING_ID:
        return explicit
    parent_tree = membership.get(entity_id, "")
    if parent_tree:
        return resolve_effective_ring_id(
            parent_tree,
            explicit_ring_ids=explicit_ring_ids,
            membership=membership,
            is_tree=is_tree,
            _visited=_visited,
        )
    return UNCLASSIFIED_RING_ID


def clamp_to_band(
    x: float,
    y: float,
    band: RingBand,
    *,
    margin: float = 24.0,
) -> tuple[float, float, bool]:
    """Devuelve (x, y, clamped): posición corregida a la banda del anillo.

    Clamp de POSICIÓN suave: si el punto está fuera de [inner+m, outer-m],
    se reproyecta sobre el borde más cercano manteniendo el ángulo. El
    margen evita que los items se peguen a las fronteras visuales.
    """
    import math

    dist = math.hypot(x, y)
    inner = max(0.0, band.inner_radius + margin)
    outer = max(inner, band.outer_radius - margin)
    if dist < 1e-9:
        # En el centro exacto: proyectar al target en dirección fija
        return band.target_radius, 0.0, True
    if dist < inner:
        scale = inner / dist
        return x * scale, y * scale, True
    if dist > outer:
        scale = outer / dist
        return x * scale, y * scale, True
    return x, y, False
