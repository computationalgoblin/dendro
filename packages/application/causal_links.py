"""Hilo causal setup→payoff: UNA sola definición de hijos, cadena e hilos sueltos.

BETA2-FIX-09 (G2-15, parte causal).

**Decisión de diseño** (la que pedía elegir el ticket, y la que queda escrita):
la FUENTE DE VERDAD del enlace causal es ``causal_parent_hito_ids`` —el lado que
el autor declara de forma natural («este hito recoge lo que plantó aquel») y el
único que llenaban las cuatro rutas de escritura (`create_hito_manual`,
`approve_hito`, `accept_candidate`, `update_hito`)—. Los **hijos son un índice
DERIVADO** de los padres, exactamente como ya hacía de facto
``NarrativeImpactService._milestone_dependents``.

Consecuencias de la elección:

- **No hay cuatro puntos de escritura** que mantener en sincronía, así que los
  datos no pueden volver a divergir.
- **Los proyectos ya guardados se reparan solos** (los 8 mundos del beta, schema
  v40): la cadena se lee derivándola de los padres, de modo que sale completa al
  abrir el proyecto **sin tocar el esquema** ni pedirle nada al usuario. Por eso
  este ticket NO añade migración v40→v41: no hay forma nueva en disco, y la
  reparación es de lectura.
- ``causal_child_hito_ids`` se conserva (compatibilidad de carga, export y
  cualquier lector externo) como **espejo**, reescrito por un ÚNICO punto de
  reconciliación —:func:`sync_children_mirror`—, nunca por cada servicio por su
  cuenta.

Todo lo de aquí son funciones puras sobre el proyecto (leen, y solo el par de
reconciliación escribe el espejo). Sin Qt, sin persistencia, sin IA.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "adopt_legacy_children",
    "causal_chain",
    "children_ids",
    "children_index",
    "children_of",
    "forget_child",
    "has_consequences",
    "is_frame_milestone",
    "loose_threads",
    "milestone_sort_key",
    "parents_of",
    "reconcile_causal_links",
    "sync_children_mirror",
]


def _milestones(project: Any) -> list[Any]:
    return list(getattr(project, "causal_milestones", []) or [])


def _id(hito: Any) -> str:
    return str(getattr(hito, "id", "") or "")


def _parent_ids(hito: Any) -> list[str]:
    return [str(pid) for pid in (getattr(hito, "causal_parent_hito_ids", []) or []) if str(pid)]


def _mirror_ids(hito: Any) -> list[str]:
    return [str(cid) for cid in (getattr(hito, "causal_child_hito_ids", []) or []) if str(cid)]


def milestone_sort_key(hito: Any) -> tuple[int, float, float, str]:
    """Clave de orden CRONOLÓGICO de un hito (año primero, `sort_index` desempata).

    Definición única compartida: ``ChronologyWalkService._sort_key`` delega aquí
    (era la misma semántica escrita dos veces, y `list_causal_chain` no usaba
    ninguna: devolvía la cadena en anchura, con el payoff ahogado entre trece
    episodios). Los hitos sin año entero van DESPUÉS de los datados.
    """
    meta = getattr(hito, "metadata", None) or {}
    try:
        tiebreak = float(meta.get("sort_index", 0) or 0)
    except (TypeError, ValueError, AttributeError):
        tiebreak = 0.0
    title = str(getattr(hito, "title", ""))
    year = getattr(hito, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        return (0, float(year), tiebreak, title)
    return (1, 0.0, tiebreak, title)


def children_index(project: Any) -> dict[str, list[str]]:
    """Índice ``{id del padre: [ids de sus consecuencias]}`` derivado de los padres.

    Es LA respuesta a «hijos de un hito» en toda la aplicación: servicio,
    reviewer, walk y UI la consumen. No lee ``causal_child_hito_ids``.
    """
    index: dict[str, list[str]] = {}
    for hito in _milestones(project):
        child_id = _id(hito)
        if not child_id:
            continue
        for parent_id in _parent_ids(hito):
            bucket = index.setdefault(parent_id, [])
            if child_id not in bucket:
                bucket.append(child_id)
    return index


def children_ids(project: Any, hito_id: str) -> list[str]:
    """Ids de las consecuencias directas de ``hito_id`` (orden cronológico)."""
    target = str(hito_id or "")
    if not target:
        return []
    by_id = {_id(h): h for h in _milestones(project)}
    ids = children_index(project).get(target, [])
    ordered = sorted(
        (by_id[cid] for cid in ids if cid in by_id),
        key=milestone_sort_key,
    )
    return [_id(h) for h in ordered]


def children_of(project: Any, hito_id: str) -> list[Any]:
    """Consecuencias directas de ``hito_id`` como hitos, en orden cronológico."""
    by_id = {_id(h): h for h in _milestones(project)}
    return [by_id[cid] for cid in children_ids(project, hito_id) if cid in by_id]


def parents_of(project: Any, hito_id: str) -> list[Any]:
    """Hitos que este hito recoge (sus causas declaradas), en orden cronológico."""
    by_id = {_id(h): h for h in _milestones(project)}
    hito = by_id.get(str(hito_id or ""))
    if hito is None:
        return []
    parents = [by_id[pid] for pid in _parent_ids(hito) if pid in by_id]
    return sorted(parents, key=milestone_sort_key)


def has_consequences(project: Any, hito: Any) -> bool:
    """¿Algún hito posterior declara a este como causa?

    Única definición de «tiene consecuencias» del repo. Mide **hijos causales**,
    no ``caused_relation_ids`` (que explican el grafo de relaciones, no cierran
    un hilo narrativo): esa confusión era justo el bug de
    ``find_hitos_without_consequences`` (20 de 20 hitos «sin consecuencias»).
    """
    return bool(children_index(project).get(_id(hito)))


def causal_chain(project: Any, hito_id: str) -> list[Any]:
    """``hito_id`` + todas sus consecuencias (transitivas), en orden CRONOLÓGICO.

    El orden es el canónico (:func:`milestone_sort_key`: año, luego
    ``sort_index``) con un desempate propio de la cadena: la **profundidad
    causal**. Entre hitos del mismo año —o entre hitos SIN datar, donde el año no
    dice nada— una consecuencia nunca se lista por delante de su causa; el
    desempate por título solo queda para lo verdaderamente empatado.

    Tolera ciclos declarados por error (conjunto ``visto``) y devuelve lista
    vacía si el hito no existe.
    """
    by_id = {_id(h): h for h in _milestones(project)}
    start = str(hito_id or "")
    if start not in by_id:
        return []
    index = children_index(project)
    profundidad: dict[str, int] = {}
    pendientes = [(start, 0)]
    while pendientes:
        current, nivel = pendientes.pop(0)
        if current in profundidad or current not in by_id:
            continue
        profundidad[current] = nivel
        pendientes.extend((cid, nivel + 1) for cid in index.get(current, []))

    def _clave(hito: Any) -> tuple[int, float, float, int, str]:
        bucket, year, tiebreak, title = milestone_sort_key(hito)
        return (bucket, year, tiebreak, profundidad.get(_id(hito), 0), title)

    return sorted((by_id[mid] for mid in profundidad), key=_clave)


def is_frame_milestone(project: Any, hito: Any) -> bool:
    """¿Es un hito-marco (contiene subhitos)? Eje de contención, no causal."""
    target = _id(hito)
    if not target:
        return False
    return any(
        str(getattr(other, "parent_milestone_id", "") or "") == target
        for other in _milestones(project)
    )


def loose_threads(project: Any) -> list[Any]:
    """«Plantado sin recoger»: hitos que ningún hito posterior recoge.

    Definición elegida (la pregunta abierta del ticket, decidida aquí y escrita
    en su cierre): **hito sin consecuencias causales, excluyendo los
    hitos-marco**. Los marcos (`TEMPORADA 1`, `TEMPORADA 2` en el mundo del
    tester) son contención temporal, no setups, y solo metían ruido.

    Se prefiere a «con padre y sin hijos» porque esa dejaba fuera al setup RAÍZ
    que nadie recoge —un hito sin padre y sin hijos es precisamente una semilla
    plantada y olvidada—, y sobre el mundo del tester da el mismo resultado útil
    (`2x08 — Habitable`, el final de serie) en vez de los 20 de 20 de antes.
    """
    index = children_index(project)  # una sola pasada, no una por hito
    marcos = {
        str(getattr(h, "parent_milestone_id", "") or "")
        for h in _milestones(project)
        if getattr(h, "parent_milestone_id", None)
    }
    return sorted(
        (
            hito
            for hito in _milestones(project)
            if not index.get(_id(hito)) and _id(hito) not in marcos
        ),
        key=milestone_sort_key,
    )


# ── reconciliación: el ÚNICO punto que escribe el espejo ────────────────────


def forget_child(project: Any, parent_id: str, child_id: str) -> None:
    """Borra ``child_id`` del espejo de ``parent_id`` (paso previo a deshacer).

    Las rutas que QUITAN un enlace tienen que limpiar también el espejo antes de
    reconciliar: si no, :func:`adopt_legacy_children` leería el espejo rancio
    como una declaración del autor y resucitaría el enlace recién deshecho.
    """
    parent = str(parent_id or "")
    child = str(child_id or "")
    if not parent or not child:
        return
    for hito in _milestones(project):
        if _id(hito) != parent:
            continue
        hito.causal_child_hito_ids = [cid for cid in _mirror_ids(hito) if cid != child]


def adopt_legacy_children(project: Any) -> int:
    """Pasa a la fuente de verdad los enlaces escritos SOLO en el espejo.

    Un proyecto editado a mano (o reparado a mano, como hizo el tester en su
    sesión 2) puede traer ``causal_child_hito_ids`` sin el ``causal_parent_hito_ids``
    recíproco. Derivar sin más lo perdería: aquí se adopta como padre, que es lo
    mismo que el autor quiso decir. Devuelve cuántos enlaces se adoptaron.
    """
    by_id = {_id(h): h for h in _milestones(project)}
    adoptados = 0
    for hito in _milestones(project):
        parent_id = _id(hito)
        for child_id in _mirror_ids(hito):
            child = by_id.get(child_id)
            if child is None or child_id == parent_id:
                continue
            if parent_id in _parent_ids(child):
                continue
            child.causal_parent_hito_ids = [*_parent_ids(child), parent_id]
            adoptados += 1
    return adoptados


def sync_children_mirror(project: Any) -> bool:
    """Reescribe ``causal_child_hito_ids`` como espejo derivado de los padres.

    Es una re-derivación TOTAL (no acumula): lo que no está declarado en algún
    ``causal_parent_hito_ids`` desaparece del espejo. Devuelve ``True`` si algo
    cambió. No llama a ``touch()``: el espejo es dato derivado, no una edición
    del autor.
    """
    index = children_index(project)
    by_id = {_id(h): h for h in _milestones(project)}
    cambio = False
    for hito in _milestones(project):
        hijos = [by_id[cid] for cid in index.get(_id(hito), []) if cid in by_id]
        derivados = [_id(h) for h in sorted(hijos, key=milestone_sort_key)]
        if _mirror_ids(hito) != derivados:
            hito.causal_child_hito_ids = derivados
            cambio = True
    return cambio


def reconcile_causal_links(project: Any) -> bool:
    """Adopta lo escrito solo en el espejo y lo reconstruye. Idempotente.

    Punto único de reconciliación: se puede llamar en cada refresco sin efectos
    acumulativos ni pérdida de datos.
    """
    adoptados = adopt_legacy_children(project)
    cambio = sync_children_mirror(project)
    return bool(adoptados) or cambio
