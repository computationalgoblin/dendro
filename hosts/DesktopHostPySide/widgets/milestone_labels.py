"""Helpers puros de etiquetado/orden de hitos causales (BETA2-UX-08).

Se extrajeron de `milestone_chronology_view.py` (la vista-lista retirada al
unificar la cronología en el lienzo lateral) a un módulo neutro para que los
paneles de detalle (hito/relación/hoja) y el gutter de la cronología no dependan
de un módulo de vista. Son funciones puras: sin Qt, solo stdlib.
"""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha1
from typing import Any


def _metadata(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def milestone_order_key(
    milestone: Any, month_names: Sequence[str] = (),
) -> tuple[int, int, float, str, str]:
    """Clave NUMÉRICA y homogénea para ordenar hitos DENTRO del mismo año.

    BETA-MULTIAGENT2-FIX-15 (G2-28): la cronología desempataba los hitos
    coetáneos con la CADENA que pinta (`sub_label`), así que «10.º» iba antes
    que «2.º» y, con calendario completo, los meses se ordenaban por su NOMBRE
    en orden alfabético. Aquí la clave es numérica y —esto es lo importante—
    SIEMPRE de la misma forma: en un mismo año pueden convivir un hito con fecha
    exacta y otro con solo `sort_index`, y compararlos no puede reventar.

    Orden: mes (índice en el calendario del proyecto; 0 = sin fecha exacta) →
    día → `metadata.sort_index` (0.0 = sin posición declarada) → título → id.
    Los dos últimos solo dan estabilidad. ``month_names`` son los meses del
    calendario del proyecto en su orden real (`CalendarConfig.month_names()`).

    NO reemplaza a :func:`milestone_sort_value` (que ordena entre AÑOS y devuelve
    un segundo elemento heterogéneo, inservible como clave de un solo `sort`):
    la complementa dentro del año, con el mismo criterio de desempate
    (`float(sort_index)`) que `ChronologyWalkService._sort_key`.
    """

    meta = _metadata(milestone)
    month_index = 0
    day = 0
    exact = meta.get("exact_date")
    if isinstance(exact, dict):
        name = str(exact.get("month", "") or "").strip()
        if name:
            names = [str(value) for value in month_names]
            if name in names:
                month_index = names.index(name) + 1  # 0 queda para "sin mes"
        try:
            day = int(exact.get("day"))
        except (TypeError, ValueError):
            day = 0
    try:
        tiebreak = float(meta.get("sort_index", 0) or 0)
    except (TypeError, ValueError):
        tiebreak = 0.0
    return (
        month_index,
        day,
        tiebreak,
        str(getattr(milestone, "title", "") or ""),
        str(getattr(milestone, "id", "") or ""),
    )


def milestone_sort_value(milestone: Any) -> tuple[int, Any, str]:
    """Clave de orden estable sin imponer un calendario gregoriano."""

    meta = _metadata(milestone)
    sort_index = meta.get("sort_index")

    # BETA1-G03: el año diegético (G02) es el tiempo canónico; el
    # sort_index manual desempata dentro del mismo año.
    year = getattr(milestone, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        try:
            tiebreak = float(sort_index)
        except (TypeError, ValueError):
            tiebreak = 0.0
        return (0, (float(year), tiebreak), str(getattr(milestone, "title", "")))
    try:
        return (0, float(sort_index), str(getattr(milestone, "title", "")))
    except (TypeError, ValueError):
        pass

    for key in ("chronology_key", "calendar_key", "calendar_date"):
        value = str(meta.get(key, "") or "").strip()
        if value:
            return (1, value.lower(), str(getattr(milestone, "title", "")))

    temporality = getattr(milestone, "temporality", None)
    for attr in ("absolute_date", "world_date", "relative_date", "period", "era"):
        value = str(getattr(temporality, attr, "") or "").strip()
        if value:
            return (2, value.lower(), str(getattr(milestone, "title", "")))

    created = str(getattr(milestone, "created_at", "") or "").strip()
    return (9, created.lower(), str(getattr(milestone, "title", "")))


def milestone_temporal_label(milestone: Any) -> str:
    meta = _metadata(milestone)
    for key in ("chronology_key", "calendar_key", "calendar_date"):
        value = str(meta.get(key, "") or "").strip()
        if value:
            return value
    exact = meta.get("exact_date")
    if isinstance(exact, dict):
        era = str(exact.get("era", "") or "").strip()
        month = str(exact.get("month", "") or "").strip()
        year = str(exact.get("year", "") or "").strip()
        day = str(exact.get("day", "") or "").strip()
        if era and month and year and day:
            return f"{era}, ano {year}, {month} {day}"
    sort_index = meta.get("sort_index")
    if sort_index not in (None, ""):
        return f"Orden {sort_index}"
    temporality = getattr(milestone, "temporality", None)
    for attr in ("absolute_date", "world_date", "relative_date", "period", "era"):
        value = str(getattr(temporality, attr, "") or "").strip()
        if value:
            return value
    # BETA1-G03: sin etiqueta manual, el año diegético ubica el hito
    year = getattr(milestone, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        return f"Año {year}"
    return "Sin ubicar"


def milestone_primary_entity_id(milestone: Any) -> str:
    meta = _metadata(milestone)
    explicit = str(meta.get("primary_entity_id", "") or "").strip()
    if explicit:
        return explicit
    affected = list(getattr(milestone, "affected_entity_ids", []) or [])
    return str(affected[0]) if affected else ""


def stable_entity_color(entity: Any | None, fallback: str = "") -> str:
    """Resuelve un color de swatch desde metadatos de entidad o hash estable."""

    if entity is not None:
        meta = getattr(entity, "custom_metadata", {}) or {}
        if isinstance(meta, dict):
            for key in ("color", "ui_color", "accent_color"):
                value = str(meta.get(key, "") or "").strip()
                if value.startswith("#") and len(value) in (4, 7):
                    return value
        fallback = str(getattr(entity, "name", "") or getattr(entity, "id", "") or fallback)
    digest = sha1(str(fallback or "milestone").encode("utf-8")).hexdigest()
    palette = ["#7A733D", "#58744A", "#5F6F8F", "#8A6849", "#7C5E7F", "#4F7C78"]
    return palette[int(digest[:2], 16) % len(palette)]
