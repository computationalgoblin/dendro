"""I29 — Fase DATE: datación validada de un ``ImportGraph`` contra las eras.

Consolida y VALIDA la datación de cada candidato del grafo (la datación bruta
viene en las menciones del MAP y ya se fusiona en el REDUCE). Asigna
``DatingStatus`` (``datado`` | ``sin_datar`` | ``fuera_de_rango``):

- sin fecha → ``sin_datar`` (el texto no permite datar; NO se inventa).
- ``birth_year > death_year`` o año fuera del rango de eras → ``fuera_de_rango``.
- fecha válida dentro del rango → ``datado``.

Las **ramas** que no traen fecha propia la derivan del rango de sus miembros
(min nacimiento … máx muerte). Es no bloqueante: el commit (I28) materializa igual
los candidatos ``sin_datar``/``fuera_de_rango``; el asistente (I31) los hace visibles.

Trabaja sobre el dict de cronología que ya circula en el contexto de importación
(``chronology_applied``: ``present_year`` + ``eras``), sin acoplarse al dominio
``ProjectChronology`` (el grafo es pre-canon). La coherencia temporal de canon
(``temporal_coherence``) sigue aplicando DESPUÉS del commit.
"""

from __future__ import annotations

from typing import Any

from packages.domain.import_models import DatingStatus, ImportGraph


def _era_bounds(chronology: dict[str, Any]) -> tuple[int | None, int | None]:
    """Límites globales [min_inicio, max_fin] de las eras del proyecto.

    ``max_fin`` es ``None`` (sin tope superior) si alguna era es abierta
    (``end_year`` nulo) o si no hay eras definidas con fin.
    """
    eras = chronology.get("eras") or []
    starts: list[int] = []
    ends: list[int] = []
    has_open = False
    for era in eras:
        if not isinstance(era, dict):
            continue
        start, end = era.get("start_year"), era.get("end_year")
        if isinstance(start, int) and not isinstance(start, bool):
            starts.append(start)
        if isinstance(end, int) and not isinstance(end, bool):
            ends.append(end)
        elif end is None:
            has_open = True
    min_start = min(starts) if starts else None
    max_end = None if (has_open or not ends) else max(ends)
    return min_start, max_end


def _year_in_range(year: int, min_start: int | None, max_end: int | None) -> bool:
    if min_start is not None and year < min_start:
        return False
    if max_end is not None and year > max_end:
        return False
    return True


def _status_for(
    birth: int | None, death: int | None, min_start: int | None, max_end: int | None
) -> DatingStatus:
    if birth is None and death is None:
        return DatingStatus.SIN_DATAR
    if birth is not None and death is not None and birth > death:
        return DatingStatus.FUERA_DE_RANGO
    for year in (birth, death):
        if year is not None and not _year_in_range(year, min_start, max_end):
            return DatingStatus.FUERA_DE_RANGO
    return DatingStatus.DATADO


def apply_dating(graph: ImportGraph, *, chronology: dict[str, Any] | None = None) -> ImportGraph:
    """Valida y asigna ``dating_status`` a cada entidad del grafo (in place).

    Las ramas sin fecha propia la derivan del rango de sus miembros. No bloquea:
    solo etiqueta. Devuelve el mismo grafo para encadenar.
    """
    chronology = chronology or {}
    min_start, max_end = _era_bounds(chronology)
    by_pid = {e.provisional_id: e for e in graph.entities}

    # 1) Hojas (y ramas con fecha propia): estado directo.
    for entity in graph.entities:
        if not entity.is_branch:
            entity.dating_status = _status_for(
                entity.birth_year, entity.death_year, min_start, max_end
            )

    # 2) Ramas: derivar del rango de miembros si no traen fecha propia.
    for entity in graph.entities:
        if not entity.is_branch:
            continue
        if entity.birth_year is None and entity.death_year is None and entity.member_ids:
            births = [
                by_pid[m].birth_year for m in entity.member_ids
                if m in by_pid and by_pid[m].birth_year is not None
            ]
            deaths = [
                by_pid[m].death_year for m in entity.member_ids
                if m in by_pid and by_pid[m].death_year is not None
            ]
            if births:
                entity.birth_year = min(births)
            if deaths:
                entity.death_year = max(deaths)
        entity.dating_status = _status_for(
            entity.birth_year, entity.death_year, min_start, max_end
        )

    graph.metadata["dating_applied"] = True
    return graph
