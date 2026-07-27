"""Política de egreso de canon hacia la IA (BETA-CIERRE WS-B).

Decisión de producto: **ocultar los secretos a la IA**. El contenido de los elementos
marcados como reservados (visibilidad ``privado_autor`` / ``secreto_mundo`` /
``no_exportable`` / ``preparado_no_revelado``, o canon ``secreto_canonico``) **nunca**
se transmite al proveedor de IA, honrando la regla del repo «los secretos y la
visibilidad se respetan siempre».

Punto único de decisión (sin modelo paralelo): los constructores de contexto de IA
—``watering_service.build_watering_context``, ``WikiIndexService`` (índice compacto)
y ``WikiNavigator`` (páginas/canon/búsqueda)— consultan este módulo antes de serializar
un elemento hacia el prompt. La UI sigue viendo el canon completo; la redacción vive
en el **borde de egreso** hacia la IA, no en el modelo ni en la vista.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# Tokens de subcadena de los estados cuyo CONTENIDO no debe salir a la IA.
# Se emparejan por subcadena para tolerar tanto ``Enum`` como ``str`` y variantes.
_WITHHELD_VISIBILITY_TOKENS = ("privado", "secreto", "no_exportable", "preparado_no_revelado")
_WITHHELD_CANON_TOKENS = ("secreto_canonico",)

# Marcadores neutros que sustituyen al contenido reservado en el prompt.
REDACTED_NAME = "[reservado]"
REDACTED_LINE = "[contenido reservado — no se comparte con la IA]"


def _value_lower(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    return str(value or "").lower()


def is_withheld_from_ai(obj: Any) -> bool:
    """True si el CONTENIDO de ``obj`` no debe transmitirse a la IA.

    Tolerante a ``None`` y a objetos sin los campos (devuelve ``False``).
    """
    if obj is None:
        return False
    visibility = _value_lower(getattr(obj, "visibility_state", ""))
    if any(token in visibility for token in _WITHHELD_VISIBILITY_TOKENS):
        return True
    canon = _value_lower(getattr(obj, "canon_state", ""))
    if any(token in canon for token in _WITHHELD_CANON_TOKENS):
        return True
    return False


def relation_withheld(project: Any, rel: Any) -> bool:
    """Una relación es reservada si lo es ella o cualquiera de sus extremos.

    (El nombre de una relación revela ambos extremos; basta con que uno sea secreto.)
    """
    if is_withheld_from_ai(rel):
        return True
    entity_by_id = getattr(project, "entity_by_id", None)
    if not callable(entity_by_id):
        return False
    for endpoint_id in (getattr(rel, "source_id", None), getattr(rel, "target_id", None)):
        if endpoint_id and is_withheld_from_ai(entity_by_id(endpoint_id)):
            return True
    return False


__all__ = [
    "REDACTED_LINE",
    "REDACTED_NAME",
    "is_withheld_from_ai",
    "relation_withheld",
]
