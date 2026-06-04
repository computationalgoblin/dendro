"""Causal metadata contract for worldbuilding layers (B36-T01).

This module is the single application-layer access point for causal semantics
stored inside ``WorldLayer.metadata``. UI and AI callers must use these helpers
instead of reading/writing metadata keys directly.

MVP persistence policy: metadata values are serialized as strings so existing
``WorldLayer.metadata: dict[str, str]`` and project schema remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from packages.domain.world_layer import WorldLayer

CAUSAL_RANK_KEY = "causal_rank"
CAUSAL_ROLE_KEY = "causal_role"
CAUSAL_ALIASES_KEY = "causal_aliases"
CAUSAL_PARENT_LAYER_IDS_KEY = "causal_parent_layer_ids"
CAUSAL_NOTES_KEY = "causal_notes"


@dataclass(frozen=True)
class CausalMetadataIssue:
    """Validation issue for one world layer causal metadata entry."""

    layer_id: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "layer_id": self.layer_id,
            "field": self.field,
            "message": self.message,
        }


DEFAULT_CAUSAL_LAYER_METADATA: dict[str, dict[str, str]] = {
    "layer_premisa": {
        CAUSAL_ROLE_KEY: "meta_context",
        CAUSAL_ALIASES_KEY: "premisa estética,tono,marco creativo,atmósfera",
        CAUSAL_NOTES_KEY: "Marco creativo no diegético; informa prompts pero no actúa como causa interna del mundo.",
    },
    "layer_metafisica": {
        CAUSAL_RANK_KEY: "1",
        CAUSAL_ROLE_KEY: "root_cause",
        CAUSAL_ALIASES_KEY: "metafísica,cosmología,causas primeras,origen de la realidad",
        CAUSAL_NOTES_KEY: "Causas primeras y principios cosmológicos que condicionan todo lo inferior.",
    },
    "layer_reglas": {
        CAUSAL_RANK_KEY: "2",
        CAUSAL_ROLE_KEY: "fundamental_law",
        CAUSAL_ALIASES_KEY: "leyes fundamentales,reglas del mundo,leyes naturales,reglas mágicas",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_metafisica",
    },
    "layer_fisica": {
        CAUSAL_RANK_KEY: "3",
        CAUSAL_ROLE_KEY: "material_nature",
        CAUSAL_ALIASES_KEY: "materia,naturaleza,física,restricciones materiales",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_metafisica,layer_reglas",
    },
    "layer_geografia": {
        CAUSAL_RANK_KEY: "4",
        CAUSAL_ROLE_KEY: "geography_resources",
        CAUSAL_ALIASES_KEY: "geografía,clima,recursos,territorio",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_fisica",
    },
    "layer_biologia": {
        CAUSAL_RANK_KEY: "5",
        CAUSAL_ROLE_KEY: "life_ecology",
        CAUSAL_ALIASES_KEY: "vida,ecología,biología,especies,ecosistemas",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_fisica,layer_geografia",
    },
    "layer_lenguaje": {
        CAUSAL_RANK_KEY: "6",
        CAUSAL_ROLE_KEY: "language_symbols",
        CAUSAL_ALIASES_KEY: "lenguaje,símbolos,tradición,idiomas,signos",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_comunidades,layer_religion,layer_historia",
    },
    "layer_comunidades": {
        CAUSAL_RANK_KEY: "7",
        CAUSAL_ROLE_KEY: "cultures_societies",
        CAUSAL_ALIASES_KEY: "culturas,sociedades,comunidades,asentamientos",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_geografia,layer_biologia,layer_lenguaje",
    },
    "layer_economia": {
        CAUSAL_RANK_KEY: "8",
        CAUSAL_ROLE_KEY: "economy_politics_institutions",
        CAUSAL_ALIASES_KEY: "economía,política,instituciones,gobierno,poder",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_geografia,layer_comunidades",
    },
    "layer_religion": {
        CAUSAL_RANK_KEY: "9",
        CAUSAL_ROLE_KEY: "religion_myth_ideology",
        CAUSAL_ALIASES_KEY: "religión,mito,ideología,creencias",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_metafisica,layer_comunidades,layer_historia",
    },
    "layer_tecnologia": {
        CAUSAL_RANK_KEY: "10",
        CAUSAL_ROLE_KEY: "technology_magic_power_systems",
        CAUSAL_ALIASES_KEY: "tecnología,magia,sistemas de poder,artefactos",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_reglas,layer_fisica,layer_economia",
    },
    "layer_historia": {
        CAUSAL_RANK_KEY: "11",
        CAUSAL_ROLE_KEY: "history_memory",
        CAUSAL_ALIASES_KEY: "historia,memoria,memoria colectiva,eventos históricos",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_comunidades,layer_economia,layer_religion",
    },
    "layer_conflictos": {
        CAUSAL_RANK_KEY: "12",
        CAUSAL_ROLE_KEY: "active_conflicts",
        CAUSAL_ALIASES_KEY: "conflictos activos,guerras,tensiones,disputas",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_historia,layer_economia,layer_religion",
    },
    "layer_narrativa": {
        CAUSAL_RANK_KEY: "13",
        CAUSAL_ROLE_KEY: "narrative_plots_characters",
        CAUSAL_ALIASES_KEY: "narrativa,tramas,personajes,facciones,escenas",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_conflictos,layer_historia,layer_situacion",
    },
    "layer_situacion": {
        CAUSAL_RANK_KEY: "14",
        CAUSAL_ROLE_KEY: "status_quo",
        CAUSAL_ALIASES_KEY: "situación actual,status quo,equilibrio presente,estado actual",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_historia,layer_conflictos,layer_economia",
    },
    "layer_campaña": {
        CAUSAL_RANK_KEY: "15",
        CAUSAL_ROLE_KEY: "play_consequence",
        CAUSAL_ALIASES_KEY: "campaña,sesiones,consecuencias de juego,partida",
        CAUSAL_PARENT_LAYER_IDS_KEY: "layer_narrativa,layer_situacion,layer_conflictos",
        CAUSAL_NOTES_KEY: "Capa de uso en campaña; B36 no implementa ni modifica Sesión.",
    },
}


def _metadata(layer: WorldLayer) -> dict[str, str]:
    meta = getattr(layer, "metadata", None)
    if not isinstance(meta, dict):
        layer.metadata = {}
    return layer.metadata


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _set_csv(layer: WorldLayer, key: str, values: Iterable[str]) -> None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    meta = _metadata(layer)
    if cleaned:
        meta[key] = ",".join(cleaned)
    else:
        meta.pop(key, None)


def get_causal_rank(layer: WorldLayer) -> int | None:
    """Return the layer explanatory rank, or None for non-causal/meta layers."""
    raw = _metadata(layer).get(CAUSAL_RANK_KEY)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def set_causal_rank(layer: WorldLayer, rank: int | None) -> None:
    """Set causal rank as a serialized string; None removes the rank."""
    meta = _metadata(layer)
    if rank is None:
        meta.pop(CAUSAL_RANK_KEY, None)
        return
    meta[CAUSAL_RANK_KEY] = str(int(rank))


def get_causal_role(layer: WorldLayer) -> str | None:
    value = _metadata(layer).get(CAUSAL_ROLE_KEY)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def set_causal_role(layer: WorldLayer, role: str | None) -> None:
    meta = _metadata(layer)
    cleaned = (role or "").strip()
    if cleaned:
        meta[CAUSAL_ROLE_KEY] = cleaned
    else:
        meta.pop(CAUSAL_ROLE_KEY, None)


def get_causal_aliases(layer: WorldLayer) -> list[str]:
    return _split_csv(_metadata(layer).get(CAUSAL_ALIASES_KEY))


def set_causal_aliases(layer: WorldLayer, aliases: Iterable[str]) -> None:
    _set_csv(layer, CAUSAL_ALIASES_KEY, aliases)


def get_causal_parent_layer_ids(layer: WorldLayer) -> list[str]:
    return _split_csv(_metadata(layer).get(CAUSAL_PARENT_LAYER_IDS_KEY))


def set_causal_parent_layer_ids(layer: WorldLayer, layer_ids: Iterable[str]) -> None:
    _set_csv(layer, CAUSAL_PARENT_LAYER_IDS_KEY, layer_ids)


def get_causal_notes(layer: WorldLayer) -> str:
    return str(_metadata(layer).get(CAUSAL_NOTES_KEY, "") or "")


def set_causal_notes(layer: WorldLayer, notes: str | None) -> None:
    meta = _metadata(layer)
    cleaned = (notes or "").strip()
    if cleaned:
        meta[CAUSAL_NOTES_KEY] = cleaned
    else:
        meta.pop(CAUSAL_NOTES_KEY, None)


def is_causally_above(layer_a: WorldLayer, layer_b: WorldLayer) -> bool:
    """Return True if layer_a has a lower explanatory rank than layer_b."""
    rank_a = get_causal_rank(layer_a)
    rank_b = get_causal_rank(layer_b)
    return rank_a is not None and rank_b is not None and rank_a < rank_b


def is_causally_below(layer_a: WorldLayer, layer_b: WorldLayer) -> bool:
    """Return True if layer_a has a higher explanatory rank than layer_b."""
    rank_a = get_causal_rank(layer_a)
    rank_b = get_causal_rank(layer_b)
    return rank_a is not None and rank_b is not None and rank_a > rank_b


def sort_layers_by_causal_rank(layers: Iterable[WorldLayer]) -> list[WorldLayer]:
    """Sort causal layers by rank; unranked/meta layers go after ranked layers."""
    def key(layer: WorldLayer) -> tuple[int, int, str]:
        rank = get_causal_rank(layer)
        if rank is None:
            return (1, int(getattr(layer, "order", 0) or 0), str(getattr(layer, "name", "")).lower())
        return (0, rank, str(getattr(layer, "name", "")).lower())

    return sorted(list(layers), key=key)


def apply_default_causal_metadata(layers: Iterable[WorldLayer], *, overwrite: bool = False) -> None:
    """Apply B36 default causal metadata to known default layer IDs.

    Existing custom metadata is preserved by default. Set overwrite=True only for
    explicit reset/migration tooling.
    """
    for layer in layers:
        defaults = DEFAULT_CAUSAL_LAYER_METADATA.get(str(getattr(layer, "id", "")))
        if not defaults:
            continue
        meta = _metadata(layer)
        for key, value in defaults.items():
            if overwrite or not str(meta.get(key, "")).strip():
                meta[key] = value


def causal_layer_summary(layer: WorldLayer) -> dict[str, Any]:
    """Return a safe causal summary for contexts/UI without exposing raw metadata."""
    return {
        "id": getattr(layer, "id", ""),
        "name": getattr(layer, "name", ""),
        "order": getattr(layer, "order", 0),
        "causal_rank": get_causal_rank(layer),
        "causal_role": get_causal_role(layer),
        "causal_aliases": get_causal_aliases(layer),
        "causal_parent_layer_ids": get_causal_parent_layer_ids(layer),
        "causal_notes": get_causal_notes(layer),
    }


def validate_causal_metadata(layers: Iterable[WorldLayer]) -> list[CausalMetadataIssue]:
    """Validate causal metadata consistency without mutating layers."""
    layer_list = list(layers)
    layer_ids = {str(getattr(layer, "id", "")) for layer in layer_list}
    ranked: dict[int, str] = {}
    issues: list[CausalMetadataIssue] = []

    for layer in layer_list:
        layer_id = str(getattr(layer, "id", ""))
        raw_rank = _metadata(layer).get(CAUSAL_RANK_KEY)
        rank = get_causal_rank(layer)
        role = get_causal_role(layer)

        if raw_rank is not None and str(raw_rank).strip() and rank is None:
            issues.append(CausalMetadataIssue(layer_id, CAUSAL_RANK_KEY, "causal_rank must be an integer string"))
        if rank is not None:
            if rank < 1:
                issues.append(CausalMetadataIssue(layer_id, CAUSAL_RANK_KEY, "causal_rank must be >= 1"))
            elif rank in ranked:
                issues.append(CausalMetadataIssue(layer_id, CAUSAL_RANK_KEY, f"duplicate causal_rank also used by {ranked[rank]}"))
            else:
                ranked[rank] = layer_id
        if rank is not None and not role:
            issues.append(CausalMetadataIssue(layer_id, CAUSAL_ROLE_KEY, "ranked causal layer must define causal_role"))
        if role and any(ch.isspace() for ch in role):
            issues.append(CausalMetadataIssue(layer_id, CAUSAL_ROLE_KEY, "causal_role should be a compact token without whitespace"))
        for parent_id in get_causal_parent_layer_ids(layer):
            if parent_id not in layer_ids:
                issues.append(CausalMetadataIssue(layer_id, CAUSAL_PARENT_LAYER_IDS_KEY, f"unknown parent layer id: {parent_id}"))
            elif parent_id == layer_id:
                issues.append(CausalMetadataIssue(layer_id, CAUSAL_PARENT_LAYER_IDS_KEY, "layer cannot be its own causal parent"))

    return issues
