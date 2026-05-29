"""
World layer dataclass — §10.3.

Provides ``WorldLayer``, a customizable classification layer for worldbuilding,
and ``default_world_layers()`` that returns the 16 predefined layers.

Pure domain model — stdlib only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorldLayer:
    """A worldbuilding classification layer (§10.3).

    Layers allow entities and relations to be classified by conceptual depth
    (geography, biology, politics, etc.) rather than by fixed entity type.

    Attributes:
        id: Unique identifier (semantic for defaults, UUID for user-created).
        name: Human-readable display name.
        description: What this layer covers (freeform).
        order: Display/priority order (lower = first). Duplicates allowed;
            secondary sort is by name.
        is_visible: Whether this layer is visible in UIs and assignable.
        is_default: True for the 16 predefined layers, False for user-created.
        metadata: Extensible key-value metadata.
    """

    id: str
    name: str
    description: str = ""
    order: int = 0
    is_visible: bool = True
    is_default: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "is_visible": self.is_visible,
            "is_default": self.is_default,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLayer:
        """Deserialize from a dictionary, tolerating missing keys."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            order=data.get("order", 0),
            is_visible=data.get("is_visible", True),
            is_default=data.get("is_default", False),
            metadata=dict(data.get("metadata", {})),
        )


def default_world_layers() -> list[WorldLayer]:
    """Return the 16 predefined world layers from §10.3.

    Each layer has:
    - A semantic ID (``layer_*``) for stable referencing
    - ``is_default=True``
    - Correct order matching the contract

    These are the canonical defaults; users can hide, reorder, or add
    custom layers on top.
    """
    return [
        WorldLayer(
            id="layer_premisa",
            name="Premisa estética y tonal",
            description="Estilo visual, atmósfera, tono narrativo y premisa estética del mundo",
            order=1,
            is_default=True,
        ),
        WorldLayer(
            id="layer_metafisica",
            name="Metafísica y cosmología",
            description="Origen del universo, planos de existencia, naturaleza del ser y la realidad",
            order=2,
            is_default=True,
        ),
        WorldLayer(
            id="layer_reglas",
            name="Reglas fundamentales",
            description="Reglas básicas del mundo: cómo funciona la magia, la tecnología, las leyes naturales",
            order=3,
            is_default=True,
        ),
        WorldLayer(
            id="layer_fisica",
            name="Física y restricciones materiales",
            description="Leyes físicas, materiales disponibles, limitaciones del mundo físico",
            order=4,
            is_default=True,
        ),
        WorldLayer(
            id="layer_geografia",
            name="Geografía, clima y recursos",
            description="Mapas, regiones, climas, recursos naturales, distribución geográfica",
            order=5,
            is_default=True,
        ),
        WorldLayer(
            id="layer_biologia",
            name="Biología, especies y ecologías",
            description="Especies, razas, ecosistemas, cadenas alimenticias, biodiversidad",
            order=6,
            is_default=True,
        ),
        WorldLayer(
            id="layer_comunidades",
            name="Comunidades, culturas y sociedades",
            description="Asentamientos, tradiciones culturales, estructuras sociales, demografía",
            order=7,
            is_default=True,
        ),
        WorldLayer(
            id="layer_economia",
            name="Economía, política e instituciones",
            description="Sistemas económicos, gobierno, leyes, instituciones, poder político",
            order=8,
            is_default=True,
        ),
        WorldLayer(
            id="layer_lenguaje",
            name="Lenguaje, símbolos y tradición",
            description="Idiomas, escritura, simbolismo, tradición oral, heráldica",
            order=9,
            is_default=True,
        ),
        WorldLayer(
            id="layer_religion",
            name="Religión, mito e ideología",
            description="Creencias religiosas, mitos fundacionales, ideologías, filosofías",
            order=10,
            is_default=True,
        ),
        WorldLayer(
            id="layer_tecnologia",
            name="Tecnología, magia y sistemas de poder",
            description="Nivel tecnológico, sistemas mágicos, artefactos, fuentes de poder",
            order=11,
            is_default=True,
        ),
        WorldLayer(
            id="layer_historia",
            name="Historia y memoria colectiva",
            description="Eventos históricos, eras, guerras, migraciones, memoria cultural",
            order=12,
            is_default=True,
        ),
        WorldLayer(
            id="layer_situacion",
            name="Situación actual",
            description="Estado actual del mundo, equilibrio de poder, tensiones presentes",
            order=13,
            is_default=True,
        ),
        WorldLayer(
            id="layer_conflictos",
            name="Conflictos activos",
            description="Guerras en curso, conflictos políticos, disputas territoriales, tensiones",
            order=14,
            is_default=True,
        ),
        WorldLayer(
            id="layer_narrativa",
            name="Narrativa, trama y escenas",
            description="Estructura narrativa, arcos argumentales, personajes principales, escenas clave",
            order=15,
            is_default=True,
        ),
        WorldLayer(
            id="layer_campaña",
            name="Campaña, sesiones y consecuencias",
            description="Sesiones de juego, decisiones de jugadores, consecuencias, evolución de la campaña",
            order=16,
            is_default=True,
        ),
    ]
