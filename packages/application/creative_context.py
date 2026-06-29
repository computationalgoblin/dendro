"""Creative context helpers (PA04).

Convierten la configuración creativa canónica del proyecto en un brief compacto y
provider-safe para los prompts de IA. Nunca mutan canon ni persistencia.

PA04 simplificó la configuración a 30 campos en 5 secciones tipadas
(``creative_config``: identidad/direccion/motor/estilo/reglas) y **eliminó** la
configuración por rama (``branch_config``) y los overrides locales. Por eso las
funciones de contexto por entidad/rama ya no devuelven overrides: se conservan
como stubs vacíos para no romper a sus llamadores (``narrative_context_builder``,
``workspaces``), pero el prompt solo lleva el perfil creativo global.
"""
from __future__ import annotations

from typing import Any, Iterable

_EMPTY = (None, "", [], {})


def _compact(section: object) -> dict[str, Any]:
    """Mantiene solo las claves con valor no vacío."""
    if not isinstance(section, dict):
        return {}
    return {k: v for k, v in section.items() if v not in _EMPTY}


def project_creative_brief(project) -> dict[str, Any]:
    """Devuelve el perfil creativo global del proyecto para la IA (PA04).

    Compacto y tipado: identidad + dirección + motor narrativo + estilo/tono +
    reglas. Solo incluye secciones con algún campo relleno.
    """
    if project is None:
        return {}
    cc = getattr(project, "creative_config", None)
    to_dict = getattr(cc, "to_dict", None)
    data = to_dict() if callable(to_dict) else {}
    data = data if isinstance(data, dict) else {}

    brief: dict[str, Any] = {
        "project_name": getattr(project, "name", ""),
        "primary_language": getattr(project, "primary_language", "es"),
        "project_type": getattr(project, "project_type", ""),
        "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False)),
    }
    for section in ("identidad", "direccion", "motor", "estilo", "reglas"):
        compact = _compact(data.get(section))
        if compact:
            brief[section] = compact
    return brief


def selected_branch_creative_context(
    project, selected_entity_ids: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """PA04: la configuración por rama se eliminó. Sin overrides locales."""
    return []


def selected_entity_creative_context(
    project, selected_entity_ids: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """PA04: la configuración por entidad/rama se eliminó. Sin overrides locales."""
    return []
