"""Presupuesto de tokens configurable para el prompt de la command bar.

El usuario fija un total de tokens de contexto (vía el tuner de la UI o el
default del proyecto). El sistema lo reparte porcentualmente entre las secciones
del "cono de autoridad" y trunca lo que exceda. El prompt del usuario es sagrado:
jamás se trunca.

Reparto porcentual de referencia (sobre el total disponible; el prompt del
usuario queda fuera del budget):

                      % del budget    qué es
    ──────────────────────────────────────────────────────
    directivas              4%        count, @refs, modo (DIRIGE)
    menciones               4%        mini-fichas @ (DIRIGE)
    cerco_canon            14%        hard_rules, negative_space (RESTRINGE)
    posicion_causal        13%        anillos→ramas→hojas (RESTRINGE)
    seleccion              15%        entidad objetivo (INFORMA)
    vecindario             20%        vecinos con decaimiento (INFORMA)
    parametros_permanentes 10%        género/tono/estilo (ATMÓSFERA)
    contexto_autorizado    20%        resto del scope sin duplicados (RESIDUAL)
    ──────────────────────────────────────────────────────
    TOTAL                 100%        (prompt del usuario = sagrado, fuera del budget)

El presupuesto controla SOLO el contexto construido por la app. El RAG mantiene
su propio token_budget independiente (1800-3200 por estrategia).
"""

from __future__ import annotations

import copy
import json
from typing import Any

# Default si ni el tuner ni el proyecto lo fijan.
DEFAULT_PROMPT_BUDGET_TOKENS = 4000

# Reparto porcentual del cono de autoridad.
# Sobre el total disponible (excluye el prompt del usuario, que es sagrado).
SECTION_PERCENTAGES: dict[str, float] = {
    # --- DIRIGE (8%) ---
    "directivas": 0.04,
    "menciones": 0.04,
    # --- RESTRINGE (27%) ---
    "cerco_canon": 0.14,
    "posicion_causal": 0.13,
    # --- INFORMA (35%) ---
    "seleccion": 0.15,
    "vecindario": 0.20,
    # --- ATMÓSFERA (10%) ---
    "parametros_permanentes": 0.10,
    # --- RESIDUAL (20%) ---
    "contexto_autorizado": 0.20,
}
# Suma = 1.00

# Secciones cuyo contenido es sagrado (nunca se trunca).
SACRED_SECTIONS = frozenset({"prompt_exacto_usuario", "formatos_h05"})


def tokens_to_chars(tokens: int) -> int:
    """Aproximación: 1 token ≈ 3.5 chars en español."""
    return int(tokens * 3.5)


def truncate_to_chars(text: str, max_chars: int) -> str:
    """Trunca respetando límite de palabra. Añade '…' si cortó.

    Simple (sin M8): busca el último espacio antes del límite.
    """
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def enforce_budget(
    message: dict,
    total_budget_tokens: int,
    section_percentages: dict[str, float] | None = None,
) -> dict:
    """Aplica un reparto porcentual al total y trunca cada sección.

    1. Calcula chars disponibles por sección = tokens_to_chars(total * percentage).
    2. Las secciones en SACRED_SECTIONS se dejan intactas.
    3. Las secciones string → truncate_to_chars.
    4. Las secciones list/dict → json.dumps + truncate_to_chars + json.loads
       (si el JSON truncado no parsea, se queda como string truncado).
    5. Las secciones None/vacías → se omiten del resultado.
    6. No muta la entrada; devuelve una copia.

    ``section_percentages`` permite un reparto por intent (perfil por tier). Si
    es None se usa :data:`SECTION_PERCENTAGES` global y las secciones sin
    porcentaje pasan intactas (compatibilidad hacia atrás). Si se pasa un perfil
    explícito, es un WHITELIST: las secciones presentes en el mensaje pero
    ausentes del perfil se OMITEN (no son relevantes para ese tipo de tarea).
    """
    if not isinstance(message, dict):
        return message
    total = int(total_budget_tokens or DEFAULT_PROMPT_BUDGET_TOKENS)
    percentages = SECTION_PERCENTAGES if section_percentages is None else section_percentages
    explicit_profile = section_percentages is not None
    result: dict[str, Any] = {}
    for key, value in message.items():
        # Sagrado: copia intacta.
        if key in SACRED_SECTIONS:
            result[key] = copy.deepcopy(value)
            continue
        # None / vacíos: se omiten.
        if value is None:
            continue
        if isinstance(value, (str, list, dict, tuple)) and len(value) == 0:
            continue
        pct = percentages.get(key)
        if pct is None:
            # Perfil explícito = whitelist: lo no listado se omite. Con el
            # reparto global por defecto, se deja intacto (no controlado).
            if explicit_profile:
                continue
            result[key] = copy.deepcopy(value)
            continue
        max_chars = tokens_to_chars(int(total * pct))
        if isinstance(value, str):
            result[key] = truncate_to_chars(value, max_chars)
            continue
        # list / dict / tuple: serializar, truncar, reparsear.
        serialized = json.dumps(value, ensure_ascii=False)
        if len(serialized) <= max_chars:
            result[key] = copy.deepcopy(value)
            continue
        truncated = truncate_to_chars(serialized, max_chars)
        try:
            result[key] = json.loads(truncated)
        except (ValueError, TypeError):
            # JSON truncado no parsea → se queda como string truncado.
            result[key] = truncated
    return result
