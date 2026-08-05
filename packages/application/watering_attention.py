"""Cola de atención del riego (BETA2-JARDIN-03).

Lógica pura para el badge global «💧 N»: qué entidades están sedientas
(``falta_regar``) y en qué orden recorrerlas. Fantasmas y archivadas quedan fuera del
ciclo visible; las secadas llegan con su propio estado (``secada``) y por tanto se
excluyen solas.

BETA-MULTIAGENT2-FIX-05 (G2-07): el orden ya NO es puramente cronológico. Con 800
sedientas —entre 48 y 68 horas de reloj a los tiempos medidos en el beta— «la más
antigua primero» no es una recomendación: es una lista sin cabeza. La cola ordena
ahora por VALOR (lo que más cambia el mundo si se riega) y solo desempata por
antigüedad. ``top_thirsty`` acota además el trabajo propuesto a las N primeras.
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.application.causal_potency import get_annotated_potency

_EXCLUDED_CANON = {"fantasma", "archivado"}
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

#: Cuántas sedientas propone la app como trabajo de una tanda («las que más cambian
#: tu mundo»). No limita lo que el usuario puede regar: acota lo que se le OFRECE.
DEFAULT_TOP_THIRSTY = 10

#: Relevancia narrativa (la fija el USUARIO) → peso de prioridad. Es el mismo eje que
#: `_IMPORTANCE_SCORE` de watering_service: una entidad crítica seca duele más que una
#: menor seca, por vieja que sea la menor.
_IMPORTANCE_WEIGHT = {
    "critico": 95,
    "alto": 75,
    "medio": 50,
    "bajo": 30,
    "menor": 15,
}
_DEFAULT_IMPORTANCE_WEIGHT = 50


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


def _importance_weight(entity) -> int:
    raw = getattr(entity, "narrative_importance", None)
    key = str(getattr(raw, "value", raw) or "").strip().lower()
    return _IMPORTANCE_WEIGHT.get(key, _DEFAULT_IMPORTANCE_WEIGHT)


def _potency_weight(entity) -> int:
    """Potencia causal ATRIBUIDA por la IA al regar (§14). Sin atribuir → neutro.

    Silencio honesto, igual que el detector estructural: una entidad que la IA aún no
    ha valorado no se penaliza ni se premia; queda en la banda media.
    """
    try:
        potency = get_annotated_potency(entity)
    except Exception:  # noqa: BLE001 — la prioridad nunca rompe el badge
        return _DEFAULT_IMPORTANCE_WEIGHT
    return _DEFAULT_IMPORTANCE_WEIGHT if potency is None else int(potency)


def thirsty_priority(entity, report) -> tuple:
    """Clave de orden de la cola de sed: primero lo que MÁS cambia el mundo.

    Ejes, en orden: relevancia narrativa del usuario → potencia causal atribuida por
    la IA → antigüedad de la sed → (nombre, id) para que el recorrido sea estable
    entre refrescos y no baile bajo el cursor.
    """
    return (
        -_importance_weight(entity),
        -_potency_weight(entity),
        _sort_stamp(entity, report),
        str(getattr(entity, "name", "") or "").casefold(),
        str(getattr(entity, "id", "") or ""),
    )


def thirsty_queue(project, reports: dict) -> list[str]:
    """Ids de entidades ``falta_regar`` ordenadas por VALOR (ver ``thirsty_priority``).

    FIX-05: antes ordenaba solo por antigüedad del último diagnóstico. Ahora manda la
    relevancia narrativa y la potencia causal atribuida; la antigüedad desempata.
    """
    entities = list(getattr(project, "entities", []) or []) if project is not None else []
    ranked: list[tuple] = []
    for entity in entities:
        entity_id = str(getattr(entity, "id", "") or "")
        report = (reports or {}).get(entity_id)
        if report is None or str(getattr(report, "status", "")) != "falta_regar":
            continue
        canon = getattr(entity, "canon_state", None)
        canon_key = str(getattr(canon, "value", canon) or "").lower()
        if canon_key in _EXCLUDED_CANON:
            continue
        ranked.append((thirsty_priority(entity, report), entity_id))
    ranked.sort()
    return [entity_id for _, entity_id in ranked]


def top_thirsty(project, reports: dict, limit: int = DEFAULT_TOP_THIRSTY) -> list[str]:
    """Las ``limit`` sedientas que más cambian el mundo (cabeza de ``thirsty_queue``).

    FIX-05 (G2-07): un contador de 800 no es una lista de tareas, es una culpa
    permanente. Esta es la respuesta a «no sé cuáles diez me convienen de verdad esta
    semana»: el TRABAJO PROPUESTO es acotado aunque la deuda total sea enorme.
    """
    queue = thirsty_queue(project, reports)
    if limit is None or limit <= 0:
        return queue
    return queue[:limit]


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
