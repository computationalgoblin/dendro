"""Capa pura: vecindario por saltos (hops) con decaimiento por distancia.

Sin acceso a proyecto ni a Qt. Solo dataclasses y scoring.

Forma parte del "cono de autoridad": las entidades cercanas a la selección
pesan más que las lejanas. El decaimiento por salto se aplica al construir el
pack en ``narrative_context_builder.build_neighborhood_pack``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# hop 0 = entidad seleccionada (semilla); 1 = vecino directo; 2 = a dos saltos;
# 3 = casi nada. A partir de 4 saltos, fuera del pack (peso 0).
DECAY_BY_HOP: dict[int, float] = {0: 1.0, 1: 1.0, 2: 0.4, 3: 0.1}


def decay_weight(hop: int) -> float:
    """Peso por número de saltos desde la selección.

    hop 0 = seleccionada; 1 = vecino directo; 2 = 2 saltos; 3 = casi nada.
    Devuelve 0.0 para hop >= 4 (fuera del pack) o hop negativo.
    """
    if hop < 0:
        return 0.0
    return DECAY_BY_HOP.get(hop, 0.0)


@dataclass(frozen=True)
class NeighborhoodItem:
    """Una entidad vecina (nunca una semilla) con su peso por distancia."""

    entity_id: str
    name: str
    entity_type: str
    display_type: str
    hop: int
    weight: float
    layer_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "display_type": self.display_type,
            "hop": self.hop,
            "weight": self.weight,
            "layer_ids": list(self.layer_ids),
        }


@dataclass(frozen=True)
class NeighborhoodRelation:
    """Una relación dentro del vecindario.

    ``hop`` es el del extremo MÁS LEJANO de la selección. Una relación que toca
    una semilla cuenta como hop 1.
    """

    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    hop: int
    weight: float

    def to_dict(self) -> dict:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "hop": self.hop,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class NeighborhoodPack:
    """Resultado del BFS de vecindario para una selección."""

    items: list[NeighborhoodItem] = field(default_factory=list)
    relations: list[NeighborhoodRelation] = field(default_factory=list)
    max_hops: int = 2
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "items": [it.to_dict() for it in self.items],
            "relations": [r.to_dict() for r in self.relations],
            "max_hops": self.max_hops,
            "warnings": list(self.warnings),
        }
