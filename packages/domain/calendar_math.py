"""BETA2-CAL-01 — Aritmética pura del calendario sintético del proyecto.

Módulo de dominio (stdlib-only, sin Qt) para el calendario "por eras encadenadas":

- Las eras se encadenan por duración; el eje absoluto se deriva (``Era.start`` = suma
  de duraciones previas). El año dentro de una era numera desde 1 (estilo regnal), así
  que el mismo número de año puede existir en eras distintas.
- Los meses son **globales** (una sola lista de meses con su longitud para todo el
  calendario), por lo que los días-por-año son constantes en todas las eras.
- El día de la semana de cualquier fecha se calcula de verdad: cuenta los días
  transcurridos desde el origen (era[0], año 1, mes 1, día 1 = día absoluto 0) y aplica
  un ancla global (en qué día de la semana cae ese primer día).

Contrato: la semana solo aplica cuando hay meses y días de la semana definidos.
La envoltura ``Result`` vive en la capa de aplicación (``CalendarService``); aquí todo
es puro y determinista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


# ── Funciones puras ──────────────────────────────────────────────────────────


def days_per_year(month_lengths: list[int]) -> int:
    """Días que dura un año = suma de las longitudes de todos los meses."""
    return sum(max(0, _int(length, 0)) for length in month_lengths)


def days_since_origin(
    era_start_abs: int,
    year_within: int,
    month_index: int,
    day: int,
    month_lengths: list[int],
) -> int:
    """Días transcurridos desde el origen del calendario hasta (inclusive) esta fecha.

    Origen = era[0], año 1, mes 1 (index 0), día 1 → día absoluto 0.

    ``era_start_abs`` es el año absoluto en que empieza la era (suma de duraciones de las
    eras previas). ``year_within`` numera desde 1 dentro de la era. ``month_index`` es
    0-based. ``day`` numera desde 1.
    """
    absolute_year_index = era_start_abs + (year_within - 1)
    lengths = [max(0, _int(length, 0)) for length in month_lengths]
    month_offset = sum(lengths[:month_index]) if month_index > 0 else 0
    return absolute_year_index * days_per_year(lengths) + month_offset + (day - 1)


def weekday_index(days_since_origin_value: int, anchor: int, week_len: int) -> int:
    """Índice (0-based) del día de la semana para un día absoluto dado.

    ``anchor`` = índice del día de la semana en que cae el día absoluto 0.
    Lanza ``ValueError`` si ``week_len`` no es positivo (no hay semana definida).
    """
    if week_len <= 0:
        raise ValueError("week_len must be positive to compute a weekday")
    return (days_since_origin_value + anchor) % week_len


# ── Configuración normalizada de calendario (meses/semana/ancla) ─────────────


@dataclass
class CalendarConfig:
    """Config de meses/semana/ancla, normalizada y con roundtrip a ``metadata``.

    ``months`` es una lista ordenada de ``(nombre, longitud)``. ``weekdays`` es la lista
    ordenada de nombres de los días de la semana. ``week_anchor`` es el índice del día de
    la semana en que cae el primer día del calendario (día absoluto 0).
    """

    months: list[tuple[str, int]] = field(default_factory=list)
    weekdays: list[str] = field(default_factory=list)
    week_anchor: int = 0

    # -- Derivados --------------------------------------------------------------

    def month_names(self) -> list[str]:
        return [name for name, _length in self.months]

    def month_length_list(self) -> list[int]:
        return [length for _name, length in self.months]

    def has_months(self) -> bool:
        return bool(self.months)

    def has_week(self) -> bool:
        return len(self.weekdays) > 0

    def supports_exact_dates(self) -> bool:
        """La fecha exacta (mes/día/semana) solo aplica con meses y semana definidos."""
        return self.has_months() and self.has_week()

    def days_per_year(self) -> int:
        return days_per_year(self.month_length_list())

    def month_length(self, month_name: str) -> int:
        for name, length in self.months:
            if name == month_name:
                return length
        return 0

    def weekday_name(
        self,
        era_start_abs: int,
        year_within: int,
        month_name: str,
        day: int,
    ) -> str | None:
        """Nombre del día de la semana de una fecha, o ``None`` si la semana no aplica.

        Devuelve ``None`` cuando no hay meses+semana definidos o el mes no existe.
        """
        if not self.supports_exact_dates():
            return None
        names = self.month_names()
        if month_name not in names:
            return None
        month_index = names.index(month_name)
        absolute = days_since_origin(
            era_start_abs, year_within, month_index, day, self.month_length_list()
        )
        return self.weekdays[weekday_index(absolute, self.week_anchor, len(self.weekdays))]

    # -- Roundtrip --------------------------------------------------------------

    @classmethod
    def from_metadata(cls, meta: Any) -> "CalendarConfig":
        """Construye desde ``metadata`` (o su sub-dict ``calendar``) tolerando formatos legacy.

        Acepta:
        - la forma nueva normalizada (``months`` como lista de ``{name, length}`` +
          ``weekdays`` + ``week_anchor``), bien como sub-dict ``calendar`` o directamente;
        - la forma legacy del blob (``months``: lista de nombres, ``month_lengths``: dict/str,
          ``weekdays``: lista, ``days_per_month`` como defecto, sin ancla).
        """
        source: dict[str, Any] = meta if isinstance(meta, dict) else {}
        calendar = source.get("calendar")
        if isinstance(calendar, dict):
            source = calendar

        default_len = max(1, _int(source.get("days_per_month"), 30))
        months = _parse_months(source.get("months"), source.get("month_lengths"), default_len)
        weekdays = _str_list(source.get("weekdays"))
        anchor = _int(source.get("week_anchor"), 0)
        if weekdays:
            anchor = anchor % len(weekdays)
        else:
            anchor = 0
        return cls(months=months, weekdays=weekdays, week_anchor=anchor)

    def to_metadata(self) -> dict[str, Any]:
        """Serializa a la forma normalizada que vive en ``metadata['calendar']``."""
        return {
            "months": [{"name": name, "length": int(length)} for name, length in self.months],
            "weekdays": list(self.weekdays),
            "week_anchor": int(self.week_anchor),
        }


def _parse_months(months_value: Any, lengths_value: Any, default_len: int) -> list[tuple[str, int]]:
    """Normaliza los meses a lista ordenada de ``(nombre, longitud)``.

    Soporta la forma nueva (lista de dicts ``{name,length}``) y la legacy (lista de
    nombres + ``month_lengths`` como dict o texto ``"Nombre: N"``).
    """
    # Forma nueva: lista de dicts {name, length}.
    if isinstance(months_value, list) and any(isinstance(item, dict) for item in months_value):
        result: list[tuple[str, int]] = []
        for item in months_value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "").strip()
            if name:
                result.append((name, max(1, _int(item.get("length"), default_len))))
        return result

    # Forma legacy: nombres + mapa/texto de longitudes.
    names = _str_list(months_value)
    length_map = _length_map(lengths_value, default_len)
    return [(name, max(1, length_map.get(name, default_len))) for name in names]


def _length_map(value: Any, default_len: int) -> dict[str, int]:
    result: dict[str, int] = {}
    if isinstance(value, dict):
        for key, raw in value.items():
            name = str(key).strip()
            if name:
                result[name] = max(1, _int(raw, default_len))
        return result
    for line in _str_list(value):
        name = line
        length = default_len
        for separator in (":", "=", ","):
            if separator in line:
                left, right = line.split(separator, 1)
                name = left.strip()
                length = _int(right.strip(), default_len)
                break
        if name:
            result[name] = max(1, length)
    return result


__all__ = [
    "days_per_year",
    "days_since_origin",
    "weekday_index",
    "CalendarConfig",
]
