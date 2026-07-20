"""Presupuestos de contexto por tipo de tarea (tiers).

Cada intent de IA resuelve a un :class:`ContextTier` con un presupuesto de
tokens de ENTRADA (las secciones de contexto del mensaje de usuario; el system
prompt y el ``prompt_exacto_usuario`` quedan fuera, son sagrados) y de SALIDA
(``max_tokens`` del proveedor).

Filosofía: no metas todo el proyecto en cada prompt. El contexto largo
(GLOBAL/MASSIVE) se reserva para auditorías. El reparto interno
por sección lo fija :data:`INTENT_SECTION_PERCENTAGES` (un perfil por tier).

Las claves de :data:`INTENT_TO_TIER` son los valores string de ``AIJobType``
(no el enum), igual que ``INTENT_PARAMS`` en ``ai_request_gateway``, para evitar
un ciclo de imports con ``ai_jobs``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ContextTier(str, Enum):
    """Banda de presupuesto de contexto asignada a un intent."""

    FAST_LOCAL = "fast_local"
    BALANCED = "balanced"
    CAUSAL = "causal"
    SUBGRAPH = "subgraph"
    GLOBAL = "global"
    MASSIVE = "massive"


# Presupuesto de tokens de ENTRADA (solo secciones de contexto del mensaje).
TIER_INPUT_TOKENS: dict[ContextTier, int] = {
    ContextTier.FAST_LOCAL: 12_000,
    ContextTier.BALANCED: 24_000,
    ContextTier.CAUSAL: 40_000,
    ContextTier.SUBGRAPH: 80_000,
    ContextTier.GLOBAL: 200_000,
    ContextTier.MASSIVE: 600_000,
}

# Presupuesto de tokens de SALIDA (techo de max_tokens del proveedor).
TIER_OUTPUT_TOKENS: dict[ContextTier, int] = {
    ContextTier.FAST_LOCAL: 2_000,
    ContextTier.BALANCED: 4_000,
    ContextTier.CAUSAL: 6_000,
    ContextTier.SUBGRAPH: 8_000,
    ContextTier.GLOBAL: 12_000,
    ContextTier.MASSIVE: 24_000,
}

DEFAULT_TIER = ContextTier.BALANCED

# ---------------------------------------------------------------------------
# Presupuesto adaptativo (PA03): reserva fija + water-filling.
#
# El contenido FIJO/determinista del mensaje se reserva entero y NUNCA se trunca;
# el presupuesto solo reparte lo FLEXIBLE. Los porcentajes por tier aplican sobre
# el pool flexible (pool = total − reserva_fija), renormalizados a las secciones
# flexibles presentes. El sobrante de una sección que no llena su porción se
# reasigna a la sección hambrienta de MAYOR prioridad (orden de abajo).
# ---------------------------------------------------------------------------

# Secciones de contenido fijo/determinista (reservadas enteras, sagradas).
FIXED_SECTIONS: frozenset[str] = frozenset(
    {
        "prompt_exacto_usuario",
        "directivas",
        "menciones",
        "configuracion_creativa",
        "cronologia",
        # BETA2-WIKI-05: el contexto seleccionado por navegación de la wiki (páginas
        # derivadas + canon) viaja reservado entero; ya viene acotado por el presupuesto
        # del WikiNavigator. Reemplaza al antiguo volcado fijo `memoria_derivada`.
        "contexto_wiki",
        "contexto_autorizado",
        "formatos_h05",
    }
)

# Secciones flexibles ordenadas por prioridad (mayor → menor) para el
# water-filling: Selección > Canon recuperado > Candidates > Aux.
FLEXIBLE_PRIORITY_ORDER: tuple[str, ...] = (
    "seleccion",
    "canon_confirmado",
    "posicion_causal",
    "vecindario",
    "candidates_pendientes",
    "rag_auxiliar",
)

# Subconjunto flexible nutrido por la recuperación RAG (para derivar desde el
# pool el presupuesto de retrieval: "más contexto ⇒ recupera más").
_RAG_RETRIEVAL_SECTIONS: frozenset[str] = frozenset(
    {
        "canon_confirmado",
        "candidates_pendientes",
        "rag_auxiliar",
    }
)

# intent value (AIJobType.value) → tier. Asignación inicial acordada.
INTENT_TO_TIER: dict[str, ContextTier] = {
    "improve_text": ContextTier.FAST_LOCAL,
    # BETA2-FOCO: el riego usa contexto COMPACTO por entidad (nunca el proyecto entero).
    "water_entity": ContextTier.FAST_LOCAL,
    # BETA2-MEM-05: la Memoria editorial necesita más contexto causal que el riego.
    "update_memory": ContextTier.CAUSAL,
    "generate_text": ContextTier.BALANCED,
    "generate_entities": ContextTier.BALANCED,
    "generate_tree": ContextTier.BALANCED,
    "edit_entities": ContextTier.BALANCED,
    "edit_relation": ContextTier.BALANCED,
    "edit_ring": ContextTier.BALANCED,
    "edit_milestone": ContextTier.BALANCED,
    "suggest_relations": ContextTier.CAUSAL,
    "analyze_coherence": ContextTier.CAUSAL,
    "explain_from_causes": ContextTier.CAUSAL,
    "propose_milestones": ContextTier.CAUSAL,
    "create_ring_template": ContextTier.CAUSAL,
    "chronology_walk_step": ContextTier.CAUSAL,
    "expand_worldbuilding": ContextTier.SUBGRAPH,
    # BETA2-WIKI-13: la sugerencia compuesta abarca varios tipos → contexto de subgrafo.
    "suggest_composite": ContextTier.SUBGRAPH,
    "freeform_planning": ContextTier.SUBGRAPH,
    "review_graph": ContextTier.GLOBAL,
    "unknown": ContextTier.BALANCED,
}


# ---------------------------------------------------------------------------
# Perfiles de reparto por sección (uno por tier).
#
# Cada perfil es un WHITELIST + presupuesto: las secciones presentes se reparten
# el total según su porcentaje; las secciones del mensaje que NO figuran en el
# perfil se omiten (no son relevantes para ese tipo de tarea). Las secciones
# sagradas (prompt_exacto_usuario, formatos_h05) quedan siempre fuera del budget.
#
# Cada perfil suma 1.0. Las secciones nuevas etiquetadas por autoridad:
#   canon_confirmado / candidates_pendientes / rag_auxiliar
# ---------------------------------------------------------------------------

# FAST_LOCAL: ajustes pequeños (mejorar texto). El prompt del usuario es la
# estrella; el contexto es ligero y se desactivan las secciones largas.
_PROFILE_FAST: dict[str, float] = {
    "seleccion": 0.28,
    "cerco_canon": 0.20,
    "parametros_permanentes": 0.14,
    "canon_confirmado": 0.12,
    "contexto_autorizado": 0.12,
    "rag_auxiliar": 0.09,
    "directivas": 0.03,
    "menciones": 0.02,
}

# BALANCED: generación/edición normal de hojas/ramas/relaciones. Comprehensivo.
_PROFILE_BALANCED: dict[str, float] = {
    "seleccion": 0.16,
    "vecindario": 0.16,
    "cerco_canon": 0.12,
    "contexto_autorizado": 0.12,
    "canon_confirmado": 0.10,
    "parametros_permanentes": 0.08,
    "posicion_causal": 0.08,
    "rag_auxiliar": 0.10,
    "candidates_pendientes": 0.04,
    "directivas": 0.02,
    "menciones": 0.02,
}

# CAUSAL: coherencia, relaciones, causas, hitos. Prioriza selección y posición
# causal (reparto guía del contrato de fase).
_PROFILE_CAUSAL: dict[str, float] = {
    "seleccion": 0.22,
    "posicion_causal": 0.18,
    "vecindario": 0.13,
    "rag_auxiliar": 0.15,
    "cerco_canon": 0.09,
    "canon_confirmado": 0.08,
    "candidates_pendientes": 0.05,
    "parametros_permanentes": 0.04,
    "contexto_autorizado": 0.03,
    "directivas": 0.02,
    "menciones": 0.01,
}

# SUBGRAPH: rama/anillo/facción/bloque amplio. Más canon confirmado y RAG.
_PROFILE_SUBGRAPH: dict[str, float] = {
    "canon_confirmado": 0.18,
    "vecindario": 0.16,
    "seleccion": 0.14,
    "rag_auxiliar": 0.16,
    "posicion_causal": 0.10,
    "cerco_canon": 0.08,
    "contexto_autorizado": 0.08,
    "parametros_permanentes": 0.05,
    "candidates_pendientes": 0.03,
    "directivas": 0.01,
    "menciones": 0.01,
}

# GLOBAL: auditoría/revisión de proyecto. Canon + RAG dominan.
_PROFILE_GLOBAL: dict[str, float] = {
    "canon_confirmado": 0.22,
    "rag_auxiliar": 0.21,
    "vecindario": 0.12,
    "contexto_autorizado": 0.10,
    "cerco_canon": 0.10,
    "posicion_causal": 0.08,
    "candidates_pendientes": 0.06,
    "seleccion": 0.05,
    "parametros_permanentes": 0.04,
    "directivas": 0.01,
    "menciones": 0.01,
}

# Perfil por tier. MASSIVE reutiliza el reparto GLOBAL (mismo perfil de auditoría
# a gran escala; solo cambia el presupuesto total).
PROFILE_BY_TIER: dict[ContextTier, dict[str, float]] = {
    ContextTier.FAST_LOCAL: _PROFILE_FAST,
    ContextTier.BALANCED: _PROFILE_BALANCED,
    ContextTier.CAUSAL: _PROFILE_CAUSAL,
    ContextTier.SUBGRAPH: _PROFILE_SUBGRAPH,
    ContextTier.GLOBAL: _PROFILE_GLOBAL,
    ContextTier.MASSIVE: _PROFILE_GLOBAL,
}

# Reparto por intent (granularidad pedida en el contrato de fase). Se deriva del
# perfil del tier del intent; queda como dict explícito para poder sobrescribir
# un intent concreto en el futuro sin tocar el resto.
INTENT_SECTION_PERCENTAGES: dict[str, dict[str, float]] = {
    intent: PROFILE_BY_TIER[tier] for intent, tier in INTENT_TO_TIER.items()
}


def _intent_value(intent: Any) -> str:
    """Normaliza un intent (AIJobType o str) a su valor string."""
    return str(getattr(intent, "value", intent) or "unknown")


class ContextBudgetManager:
    """Resuelve tier, presupuestos de entrada/salida y reparto por sección.

    Sin estado mutable: es seguro compartir una instancia entre jobs.
    """

    def tier_for(self, intent: Any) -> ContextTier:
        """Tier base del intent (sin tener en cuenta overrides del tuner)."""
        return INTENT_TO_TIER.get(_intent_value(intent), DEFAULT_TIER)

    def input_budget(self, intent: Any, override_tokens: int | None = None) -> int:
        """Presupuesto de tokens de ENTRADA.

        El override del tuner (``prompt_budget_tokens``) se honra de forma
        literal cuando es > 0; si no, se usa el presupuesto del tier del intent.
        """
        if override_tokens and int(override_tokens) > 0:
            return int(override_tokens)
        return TIER_INPUT_TOKENS[self.tier_for(intent)]

    def output_budget(self, intent: Any) -> int:
        """Techo de tokens de SALIDA (max_tokens) según el tier del intent."""
        return TIER_OUTPUT_TOKENS[self.tier_for(intent)]

    def section_percentages(self, intent: Any) -> dict[str, float]:
        """Reparto por sección para el intent (perfil de su tier)."""
        value = _intent_value(intent)
        profile = INTENT_SECTION_PERCENTAGES.get(value)
        if profile is None:
            profile = PROFILE_BY_TIER[DEFAULT_TIER]
        return dict(profile)

    def rag_retrieval_share(self, intent: Any) -> float:
        """Fracción del presupuesto que corresponde a secciones nutridas por RAG.

        Se usa para derivar el presupuesto de recuperación desde el total: a más
        contexto declarado, más recupera el RAG (en vez de una constante fija).
        """
        profile = self.section_percentages(intent)
        share = sum(v for k, v in profile.items() if k in _RAG_RETRIEVAL_SECTIONS)
        return max(0.0, float(share))


__all__ = [
    "ContextTier",
    "TIER_INPUT_TOKENS",
    "TIER_OUTPUT_TOKENS",
    "DEFAULT_TIER",
    "INTENT_TO_TIER",
    "PROFILE_BY_TIER",
    "INTENT_SECTION_PERCENTAGES",
    "FIXED_SECTIONS",
    "FLEXIBLE_PRIORITY_ORDER",
    "ContextBudgetManager",
]
