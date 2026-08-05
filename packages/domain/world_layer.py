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


# B36-T01: seed causal metadata for the existing 16 world layers.
# Stored as strings to preserve the current Project/WorldLayer schema.
_B36_CAUSAL_DEFAULT_METADATA: dict[str, dict[str, str]] = {
    "layer_premisa": {"causal_role": "meta_context", "causal_aliases": "premisa estética,tono,marco creativo,atmósfera"},
    "layer_metafisica": {"causal_rank": "1", "causal_role": "root_cause", "causal_aliases": "metafísica,cosmología,causas primeras,origen de la realidad"},
    "layer_reglas": {"causal_rank": "2", "causal_role": "fundamental_law", "causal_aliases": "leyes fundamentales,reglas del mundo,leyes naturales,reglas mágicas", "causal_parent_layer_ids": "layer_metafisica"},
    "layer_fisica": {"causal_rank": "3", "causal_role": "material_nature", "causal_aliases": "materia,naturaleza,física,restricciones materiales", "causal_parent_layer_ids": "layer_metafisica,layer_reglas"},
    "layer_geografia": {"causal_rank": "4", "causal_role": "geography_resources", "causal_aliases": "geografía,clima,recursos,territorio", "causal_parent_layer_ids": "layer_fisica"},
    "layer_biologia": {"causal_rank": "5", "causal_role": "life_ecology", "causal_aliases": "vida,ecología,biología,especies,ecosistemas", "causal_parent_layer_ids": "layer_fisica,layer_geografia"},
    "layer_lenguaje": {"causal_rank": "6", "causal_role": "language_symbols", "causal_aliases": "lenguaje,símbolos,tradición,idiomas,signos", "causal_parent_layer_ids": "layer_comunidades,layer_religion,layer_historia"},
    "layer_comunidades": {"causal_rank": "7", "causal_role": "cultures_societies", "causal_aliases": "culturas,sociedades,comunidades,asentamientos", "causal_parent_layer_ids": "layer_geografia,layer_biologia,layer_lenguaje"},
    "layer_economia": {"causal_rank": "8", "causal_role": "economy_politics_institutions", "causal_aliases": "economía,política,instituciones,gobierno,poder", "causal_parent_layer_ids": "layer_geografia,layer_comunidades"},
    "layer_religion": {"causal_rank": "9", "causal_role": "religion_myth_ideology", "causal_aliases": "religión,mito,ideología,creencias", "causal_parent_layer_ids": "layer_metafisica,layer_comunidades,layer_historia"},
    "layer_tecnologia": {"causal_rank": "10", "causal_role": "technology_magic_power_systems", "causal_aliases": "tecnología,magia,sistemas de poder,artefactos", "causal_parent_layer_ids": "layer_reglas,layer_fisica,layer_economia"},
    "layer_historia": {"causal_rank": "11", "causal_role": "history_memory", "causal_aliases": "historia,memoria,memoria colectiva,eventos históricos", "causal_parent_layer_ids": "layer_comunidades,layer_economia,layer_religion"},
    "layer_conflictos": {"causal_rank": "12", "causal_role": "active_conflicts", "causal_aliases": "conflictos activos,guerras,tensiones,disputas", "causal_parent_layer_ids": "layer_historia,layer_economia,layer_religion"},
    "layer_narrativa": {"causal_rank": "13", "causal_role": "narrative_plots_characters", "causal_aliases": "narrativa,tramas,personajes,facciones,escenas", "causal_parent_layer_ids": "layer_conflictos,layer_historia,layer_situacion"},
    "layer_situacion": {"causal_rank": "14", "causal_role": "status_quo", "causal_aliases": "situación actual,status quo,equilibrio presente,estado actual", "causal_parent_layer_ids": "layer_historia,layer_conflictos,layer_economia"},
    "layer_campaña": {"causal_rank": "15", "causal_role": "play_consequence", "causal_aliases": "desenlace,consecuencias,secuelas,resolución", "causal_parent_layer_ids": "layer_narrativa,layer_situacion,layer_conflictos"},
}


#: BETA-AUDIT-09 — anillos con los que arranca un proyecto nuevo.
#:
#: Los 16 de ``default_world_layers()`` son el mapa causal completo del contrato §10.3
#: y siguen siendo la referencia (los usan la migración v7 y ``foco_rings``), pero
#: sembrarlos todos en un proyecto vacío abruma: un usuario nuevo abre el Mapa y ve
#: sistemas concéntricos vacíos encabezados por «Metafísica y cosmología».
#:
#: Este subconjunto usa los MISMOS ids, así que un proyecto que arranque con él y luego
#: adopte la estructura completa no duplica anillos ni pierde rangos causales.
#: Se eligen los cinco CONCRETOS y se deja fuera la cabecera abstracta (premisa,
#: metafísica, reglas, física): abrir un mundo vacío cuyo primer anillo es «Metafísica
#: y cosmología» pide una decisión que nadie tiene tomada el primer día. Quien quiera
#: el mapa causal completo lo sigue teniendo en `default_world_layers()`.
_STARTER_LAYER_IDS = (
    "layer_geografia",
    "layer_comunidades",
    "layer_historia",
    "layer_situacion",
    "layer_conflictos",
)


def starter_world_layers() -> list[WorldLayer]:
    """Subconjunto legible para un proyecto nuevo (ver ``_STARTER_LAYER_IDS``)."""
    por_id = {capa.id: capa for capa in default_world_layers()}
    elegidas = [por_id[i] for i in _STARTER_LAYER_IDS if i in por_id]
    for orden, capa in enumerate(elegidas, start=1):
        capa.order = orden
    return elegidas


def default_world_layers() -> list[WorldLayer]:
    """Return the 16 predefined world layers from §10.3.

    Each layer has:
    - A semantic ID (``layer_*``) for stable referencing
    - ``is_default=True``
    - Correct order matching the contract

    These are the canonical defaults; users can hide, reorder, or add
    custom layers on top.
    """
    layers = [
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
        # BETA-AUDIT-09: se llamaba «Campaña, sesiones y consecuencias» y hablaba de
        # «decisiones de jugadores». WS-A retiró el rol del producto, pero el copy
        # sobrevivía aquí y se sembraba en CADA proyecto nuevo: la guarda
        # tests/test_positioning_copy.py sólo recorría hosts/, no packages/.
        # El id se conserva (lo referencian la migración v7 y el mapa causal).
        WorldLayer(
            id="layer_campaña",
            name="Desenlaces y consecuencias",
            description="Cómo se resuelven las tramas: decisiones tomadas, secuelas y estado en que queda el mundo",
            order=16,
            is_default=True,
        ),
    ]
    for layer in layers:
        defaults = _B36_CAUSAL_DEFAULT_METADATA.get(layer.id)
        if defaults:
            layer.metadata.update(defaults)
    return layers
