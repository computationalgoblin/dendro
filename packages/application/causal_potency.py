"""Potencia causal por entidad y excepciones ascendentes (BETA2-MEM-08).

Modelo **ligero** (decision de entrevista): no se anaden campos de dominio ni
migracion de esquema. La potencia BASAL de una entidad y la marca de EXCEPCION
ASCENDENTE de una relacion viven en su ``custom_metadata`` (dict ya persistido),
igual que el modelo causal de capas vive en ``WorldLayer.metadata``.

- Potencia **basal**: por defecto se DERIVA del rank del anillo de la entidad
  (anillo superior = mas potencia); el usuario o la IA la pueden fijar.
- Potencia **contextual/realizada**: se infieren de forma ligera cuando se
  necesitan (no se persiste un modelo pesado).
- La potencia causal es un eje SEPARADO de la importancia narrativa
  (``NarrativeImportance``): algo puede ser causalmente menor pero central.

Las **excepciones ascendentes** (apalancamiento, catalizador, vulnerabilidad,
acumulacion, amplificacion) permiten que un cambio inferior escale a un superior;
el motor de impacto (MEM-04) las consulta ademas de ``CAUSAL_RELATION_TYPES``.
"""

from __future__ import annotations

from typing import Any

from packages.application.world_layer_causal import get_causal_rank

BASAL_POTENCY_KEY = "_causal_potency_basal"
ASCENDING_EXCEPTION_KEY = "_causal_ascending_exception"

# Tipos de excepcion ascendente nombrados por el contrato §16.
ASCENDING_EXCEPTION_TYPES: frozenset[str] = frozenset(
    {"apalancamiento", "catalizador", "vulnerabilidad", "acumulacion", "amplificacion"}
)

_DEFAULT_POTENCY = 50


def _meta(obj: Any) -> dict[str, Any]:
    meta = getattr(obj, "custom_metadata", None)
    return meta if isinstance(meta, dict) else {}


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def derive_basal_from_ring(project: Any, entity: Any) -> int:
    """Potencia basal por defecto = derivada del rank del anillo (menor rank = mayor)."""
    layers = {layer.id: layer for layer in getattr(project, "world_layers", []) or []}
    ranks = [
        rank
        for lid in (getattr(entity, "layer_ids", []) or [])
        if lid in layers and (rank := get_causal_rank(layers[lid])) is not None
    ]
    if not ranks:
        return _DEFAULT_POTENCY
    top_rank = min(ranks)  # anillo mas aguas-arriba
    return _clamp(100 - (top_rank - 1) * 6)


def get_basal_potency(project: Any, entity: Any) -> int:
    """Potencia basal de una entidad: la anotada, o la derivada del anillo."""
    raw = _meta(entity).get(BASAL_POTENCY_KEY)
    if raw is not None:
        try:
            return _clamp(int(raw))
        except (TypeError, ValueError):
            pass
    return derive_basal_from_ring(project, entity)


def get_annotated_potency(entity: Any) -> int | None:
    """Potencia basal ANOTADA (0..100) de una entidad, o ``None`` si no la tiene.

    A diferencia de ``get_basal_potency``, NO deriva del anillo: devuelve solo lo que
    se ha atribuido explícitamente (BETA2-STRUCT: la IA la fija al Regar de forma
    semántica). El detector estructural solo juzga entidades con potencia atribuida.
    """
    raw = _meta(entity).get(BASAL_POTENCY_KEY)
    if raw is None:
        return None
    try:
        return _clamp(int(raw))
    except (TypeError, ValueError):
        return None


def set_basal_potency(entity: Any, value: int | None) -> None:
    """Fija (o borra, con None) la potencia basal anotada de una entidad."""
    meta = getattr(entity, "custom_metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        entity.custom_metadata = meta
    if value is None:
        meta.pop(BASAL_POTENCY_KEY, None)
    else:
        meta[BASAL_POTENCY_KEY] = _clamp(int(value))


def get_ascending_exception(relation: Any) -> str | None:
    """Tipo de excepcion ascendente de una relacion, o None."""
    raw = _meta(relation).get(ASCENDING_EXCEPTION_KEY)
    value = str(raw or "").strip().lower()
    return value if value in ASCENDING_EXCEPTION_TYPES else None


def is_ascending_exception(relation: Any) -> bool:
    """¿Esta relacion habilita propagacion ascendente por excepcion causal?"""
    return get_ascending_exception(relation) is not None


def set_ascending_exception(relation: Any, kind: str | None) -> None:
    """Marca (o desmarca, con None) una relacion como excepcion ascendente."""
    meta = getattr(relation, "custom_metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        relation.custom_metadata = meta
    value = str(kind or "").strip().lower()
    if value in ASCENDING_EXCEPTION_TYPES:
        meta[ASCENDING_EXCEPTION_KEY] = value
    else:
        meta.pop(ASCENDING_EXCEPTION_KEY, None)


def build_ring_move_proposal(
    entity_id: str,
    *,
    current_ring_id: str = "",
    target_ring_id: str,
    context: str = "",
    reasons: list[str] | None = None,
    supporting_relation_ids: list[str] | None = None,
    expected_consequences: list[str] | None = None,
) -> dict[str, Any]:
    """proposed_data tipado de una propuesta estructural de mover-anillo (contrato §17).

    Se usa como ``proposed_data`` de un ``Candidate`` (kind='ring_move'): reutiliza el
    pipeline de candidatos (revisar/aceptar/rechazar/modificar + impacto), pero es una
    propuesta ESTRUCTURAL, no un candidato narrativo ordinario. Al aceptar mueve la
    entidad de anillo y propaga impacto.
    """
    return {
        "kind": "ring_move",
        "entity_id": entity_id,
        "current_ring_id": current_ring_id,
        "target_ring_id": target_ring_id,
        "context": context,
        "reasons": list(reasons or []),
        "supporting_relation_ids": list(supporting_relation_ids or []),
        "expected_consequences": list(expected_consequences or []),
    }


__all__ = [
    "ASCENDING_EXCEPTION_TYPES",
    "build_ring_move_proposal",
    "derive_basal_from_ring",
    "get_ascending_exception",
    "get_basal_potency",
    "is_ascending_exception",
    "set_ascending_exception",
    "set_basal_potency",
]
