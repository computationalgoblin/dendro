"""Cola de atención del riego (BETA2-JARDIN-03).

Lógica pura para el badge global «💧 N»: qué entidades están sedientas
(``falta_regar``) y en qué orden recorrerlas (la más antigua primero).
Fantasmas y archivadas quedan fuera del ciclo visible; las secadas llegan
con su propio estado (``secada``) y por tanto se excluyen solas.
"""

from __future__ import annotations

from datetime import datetime, timezone

_EXCLUDED_CANON = {"fantasma", "archivado"}
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _sort_stamp(entity, report) -> datetime:
    """Antigüedad de la sed: el último diagnóstico (aunque esté obsoleto) o,
    si nunca fue regada, la creación de la entidad."""
    latest = getattr(report, "latest", None)
    stamp = getattr(latest, "created_at", None) or getattr(entity, "created_at", None)
    if stamp is None:
        return _EPOCH
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp


def thirsty_queue(project, reports: dict) -> list[str]:
    """Ids de entidades ``falta_regar`` ordenadas de más antigua a más nueva.

    Desempate estable por (nombre en minúsculas, id) para que el recorrido
    del badge no baile entre refrescos.
    """
    entities = list(getattr(project, "entities", []) or []) if project is not None else []
    ranked: list[tuple[datetime, str, str]] = []
    for entity in entities:
        entity_id = str(getattr(entity, "id", "") or "")
        report = (reports or {}).get(entity_id)
        if report is None or str(getattr(report, "status", "")) != "falta_regar":
            continue
        canon = getattr(entity, "canon_state", None)
        canon_key = str(getattr(canon, "value", canon) or "").lower()
        if canon_key in _EXCLUDED_CANON:
            continue
        name = str(getattr(entity, "name", "") or "")
        ranked.append((_sort_stamp(entity, report), name.casefold(), entity_id))
    ranked.sort()
    return [entity_id for _, _, entity_id in ranked]


def waterable_queue(project, reports: dict) -> list[str]:
    """Ids REGABLES: ``falta_regar`` primero (más antigua 1º), luego ``regada``.

    BETA2-FOCO-34: a diferencia de ``thirsty_queue`` (solo sedientas), incluye las
    ya ``regada`` para que el badge 💧 no desaparezca tras regar y permita «Regar
    de nuevo». Excluye fantasmas/archivadas y secadas (status ``secada``).
    """
    entities = list(getattr(project, "entities", []) or []) if project is not None else []
    buckets: dict[str, list[tuple[datetime, str, str]]] = {"falta_regar": [], "regada": []}
    for entity in entities:
        entity_id = str(getattr(entity, "id", "") or "")
        report = (reports or {}).get(entity_id)
        status = str(getattr(report, "status", "")) if report is not None else ""
        if status not in buckets:
            continue
        canon = getattr(entity, "canon_state", None)
        canon_key = str(getattr(canon, "value", canon) or "").lower()
        if canon_key in _EXCLUDED_CANON:
            continue
        name = str(getattr(entity, "name", "") or "")
        buckets[status].append((_sort_stamp(entity, report), name.casefold(), entity_id))
    ordered: list[str] = []
    for status in ("falta_regar", "regada"):
        buckets[status].sort()
        ordered.extend(entity_id for _, _, entity_id in buckets[status])
    return ordered
