"""Defaults fijos de comportamiento del asistente IA (PA04).

Antes vivían en ``AIConfig`` como configuración editable por proyecto. Tras la
simplificación PA04 el comportamiento del asistente deja de ser configurable y
pasa a estas constantes en código. La configuración de proyecto queda 100%
creativa (ver [creative_config.py]).

Si en el futuro hiciera falta volver a exponer alguno, hacerlo como *ajuste de
IA* global (no como config de proyecto).
"""
from __future__ import annotations

# Número de alternativas que genera el asistente por defecto.
DEFAULT_NUM_OPTIONS: int = 3

# Formato de salida del asistente.
DEFAULT_OUTPUT_MODE: str = "contrastive_options"

# Política ante contexto insuficiente.
DEFAULT_UNCERTAINTY_POLICY: str = "conservative_proposal"

# Rol por defecto del asistente.
DEFAULT_ROLE: str = "coauthor"

# Estrategia narrativa por defecto.
DEFAULT_STRATEGY: str = "profundizar"

# Profundidad de contexto por defecto.
DEFAULT_CONTEXT_DEPTH: str = "balanced"

# Agresividad de cambios (0-10).
DEFAULT_CHANGE_AGGRESSIVENESS: int = 5

# Presupuesto de tokens de contexto por defecto para los prompts de la command bar.
DEFAULT_PROMPT_BUDGET_TOKENS: int = 4000
