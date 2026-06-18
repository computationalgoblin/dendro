"""Presupuesto de contexto adaptativo para el prompt de la command bar (PA03).

El usuario fija un total de tokens de contexto (vía el tuner de la UI o el tier
del intent). El reparto NO es un recorte rígido por porcentajes: es adaptativo.

1. **Reserva fija primero.** El contenido determinista que SIEMPRE va
   (``prompt_exacto_usuario``, ``directivas``, ``configuracion_creativa``,
   ``cronologia``, ``contexto_autorizado``…) se reserva entero y nunca se trunca.
   El presupuesto solo reparte lo que sobra: ``pool = total − reserva_fija``.
2. **Reparto inicial por %.** El ``pool`` se reparte entre las secciones
   FLEXIBLES presentes según el perfil del intent (renormalizado).
3. **Water-filling por prioridad.** Lo que le sobra a una sección que no llena su
   porción se reasigna a la sección hambrienta de MAYOR prioridad
   (:data:`FLEXIBLE_PRIORITY_ORDER`), iterando en ese orden.
4. **Recorte eliminando items enteros.** Cuando una sección flexible no cabe en
   su asignación, se descartan sus items de menor prioridad (ya vienen ordenados
   por el retrieval); nunca se parte el texto de un item a la mitad.

Si la reserva fija ya supera el total, se incluye igual (lo fijo es sagrado) y el
pool flexible queda en 0.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Any

from packages.application.context_budget import FLEXIBLE_PRIORITY_ORDER

# Default si ni el tuner ni el proyecto lo fijan.
DEFAULT_PROMPT_BUDGET_TOKENS = 4000

# 1 token ≈ 3.5 chars en español.
_CHARS_PER_TOKEN = 3.5

# Compatibilidad: secciones cuyo contenido es sagrado (subconjunto de las fijas).
SACRED_SECTIONS = frozenset({"prompt_exacto_usuario", "formatos_h05"})


def tokens_to_chars(tokens: int) -> int:
    """Aproximación: 1 token ≈ 3.5 chars en español."""
    return int(tokens * _CHARS_PER_TOKEN)


def _estimate_tokens(value: Any) -> int:
    """Tokens estimados de una sección (string o estructura serializada)."""
    if isinstance(value, str):
        chars = len(value)
    else:
        chars = len(json.dumps(value, ensure_ascii=False))
    return max(1, math.ceil(chars / _CHARS_PER_TOKEN))


def truncate_to_chars(text: str, max_chars: int) -> str:
    """Trunca respetando límite de palabra. Añade '…' si cortó."""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _trim_items_dict(section: dict, max_chars: int) -> dict:
    """Recorta una sección con lista ``items`` eliminando items enteros del final.

    Los items vienen ordenados por prioridad/score del retrieval, así que los del
    final son los menos relevantes. La etiqueta ``autoridad`` y demás claves base
    se conservan siempre.
    """
    base = {k: v for k, v in section.items() if k != "items"}
    items = section.get("items") or []
    kept: list[Any] = []
    for item in items:
        trial = dict(base)
        trial["items"] = kept + [item]
        if len(json.dumps(trial, ensure_ascii=False)) <= max_chars:
            kept.append(item)
        else:
            break
    out = dict(base)
    if kept:
        out["items"] = kept
    if len(kept) < len(items):
        out["truncado"] = True
    return out


def _trim_section(value: Any, max_tokens: int) -> Any:
    """Reduce una sección flexible a ``max_tokens`` sin partir items."""
    max_chars = tokens_to_chars(max(0, max_tokens))
    if isinstance(value, str):
        return truncate_to_chars(value, max_chars)
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return _trim_items_dict(value, max_chars)
    # Fallback para estructuras sin lista de items: serializar y truncar.
    serialized = json.dumps(value, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return value
    truncated = truncate_to_chars(serialized, max_chars)
    try:
        return json.loads(truncated)
    except (ValueError, TypeError):
        return truncated


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, (str, list, dict, tuple)) and len(value) == 0


def enforce_budget(
    message: dict,
    total_budget_tokens: int,
    section_percentages: dict[str, float] | None = None,
) -> dict:
    """Aplica el presupuesto adaptativo (reserva fija + water-filling).

    ``section_percentages`` es el perfil por intent (porcentajes por sección). Se
    usa solo para el reparto inicial del pool entre las secciones flexibles; las
    secciones fijas se reservan enteras al margen del perfil. No muta la entrada.
    """
    if not isinstance(message, dict):
        return message
    total = int(total_budget_tokens or DEFAULT_PROMPT_BUDGET_TOKENS)
    percentages = section_percentages or {}

    # 1. Clasificar secciones (omitiendo vacías/None).
    fixed: dict[str, Any] = {}
    flexible: dict[str, Any] = {}
    order: list[str] = []
    for key, value in message.items():
        if _is_empty(value):
            continue
        order.append(key)
        if key in FLEXIBLE_PRIORITY_ORDER:
            flexible[key] = value
        else:
            # Fija, sagrada o desconocida → reservada entera (nunca se trunca).
            fixed[key] = value

    # 2. Reserva fija → pool flexible.
    fixed_tokens = sum(_estimate_tokens(v) for v in fixed.values())
    pool = max(0, total - fixed_tokens)

    # 3. Reparto inicial por % (renormalizado sobre las flexibles presentes).
    present = [k for k in FLEXIBLE_PRIORITY_ORDER if k in flexible]
    weights = {k: max(0.0, float(percentages.get(k, 0.0))) for k in present}
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        weights = {k: 1.0 for k in present}
        weight_sum = float(len(present)) or 1.0
    slices = {k: pool * weights[k] / weight_sum for k in present}

    # 4. Demanda real y asignación inicial.
    demand = {k: _estimate_tokens(flexible[k]) for k in present}
    assigned = {k: min(float(demand[k]), slices[k]) for k in present}
    surplus = pool - sum(assigned.values())

    # 5. Water-filling por prioridad (present ya está en orden de prioridad).
    for key in present:
        if surplus <= 0:
            break
        need = demand[key] - assigned[key]
        if need > 0:
            give = min(need, surplus)
            assigned[key] += give
            surplus -= give

    # 6. Recortar las flexibles que no caben (eliminando items enteros).
    for key in present:
        if demand[key] > assigned[key]:
            flexible[key] = _trim_section(flexible[key], int(assigned[key]))

    # 7. Reensamblar en el orden original (sin mutar la entrada).
    result: dict[str, Any] = {}
    for key in order:
        source = flexible[key] if key in flexible else fixed[key]
        result[key] = copy.deepcopy(source)
    return result


__all__ = [
    "DEFAULT_PROMPT_BUDGET_TOKENS",
    "SACRED_SECTIONS",
    "tokens_to_chars",
    "truncate_to_chars",
    "enforce_budget",
]
