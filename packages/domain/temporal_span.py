"""Lapso temporal — BETA1-J01.

``TemporalSpan`` es el modelo de *lapso vital* reutilizable por hojas, ramas,
relaciones e hitos: un inicio (siempre presente) y un fin opcional, cada uno
descrito por un ``EventTemporality`` rico (precisión, fecha-mundo, era, notas).

El **año entero sigue siendo el eje canónico ordenable** (BETA1-G02): cada
extremo lleva su ``year: int`` dentro del ``EventTemporality``, y de ahí derivan
``start_year`` / ``end_year``. ``TemporalSpan`` es la capa descriptiva *encima*
del año, no lo reemplaza.

stdlib-only, sin dependencias externas ni de otras capas (salvo otros modelos
de dominio).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.domain.temporal_models import (
    EventTemporality,
    TemporalNature,
    TemporalPrecision,
)

# Precisiones que cuentan como "datación consciente" aunque no haya año concreto.
# OJO: UNKNOWN NO entra aquí — es también el default sin tocar, así que no puede
# distinguir 'desconocido a propósito' de 'blanco por inercia' (BETA1-J04).
_EXPLICIT_PRECISIONS: tuple[TemporalPrecision, ...] = (
    TemporalPrecision.APPROXIMATE,
    TemporalPrecision.MYTHICAL,
)


@dataclass
class TemporalSpan:
    """Lapso inicio→fin de una creación narrativa.

    - ``start``: punto temporal de inicio (siempre presente).
    - ``end``: punto temporal de fin; ``None`` si no ha terminado o se ignora
      la fecha de fin.
    - ``ongoing``: el fin está abierto explícitamente (sigue vigente).
    """

    start: EventTemporality = field(default_factory=EventTemporality)
    end: EventTemporality | None = None
    ongoing: bool = True
    # BETA1-J07: naturaleza temporal del ser (gobierna la datación coherente).
    nature: TemporalNature = TemporalNature.MORTAL

    def __post_init__(self) -> None:
        # Coherencia mínima: si hay extremo de fin, ya no está "vigente".
        if self.end is not None:
            self.ongoing = False

    # ── Naturaleza temporal (BETA1-J07) ────────────────────────────────────

    def is_immortal(self) -> bool:
        """No muere (inmortal, eterno o atemporal)."""
        return self.nature in (
            TemporalNature.INMORTAL,
            TemporalNature.ETERNO,
            TemporalNature.ATEMPORAL,
        )

    def is_eternal(self) -> bool:
        """Ni nace ni muere: origen primordial / fuera del tiempo."""
        return self.nature in (TemporalNature.ETERNO, TemporalNature.ATEMPORAL)

    # ── Eje entero (BETA1-G02) ─────────────────────────────────────────────

    @property
    def start_year(self) -> int | None:
        return self.start.year if self.start is not None else None

    @property
    def end_year(self) -> int | None:
        return self.end.year if self.end is not None else None

    def contains(self, year: int) -> bool:
        """¿*year* cae dentro del lapso? Extremos abiertos no acotan ese lado."""
        s = self.start_year
        if s is not None and year < s:
            return False
        e = self.end_year
        if e is not None and year > e:
            return False
        return True

    def is_dated(self) -> bool:
        """BETA1-J04: hay datación si el inicio porta alguna afirmación temporal
        positiva — año concreto, precisión aprox/mítica, o algún descriptor
        (fecha-mundo/absoluta/relativa, periodo o era).

        Lo que NO cuenta es el blanco-por-inercia: año ``None``, precisión por
        defecto ``UNKNOWN`` y sin ningún descriptor."""
        # BETA1-J07: un ser eterno/atemporal está datado POR SU NATURALEZA
        # (su origen es primordial; no necesita año mortal).
        if self.is_eternal():
            return True
        s = self.start
        if s is None:
            return False
        if s.year is not None:
            return True
        if s.precision in _EXPLICIT_PRECISIONS:
            return True
        return any(
            bool(x)
            for x in (s.world_date, s.absolute_date, s.relative_date, s.period, s.era)
        )

    # ── Construcción / serialización ───────────────────────────────────────

    @classmethod
    def from_years(
        cls,
        birth_year: int | None,
        death_year: int | None,
        *,
        precision: TemporalPrecision = TemporalPrecision.EXACT,
        note: str = "",
    ) -> TemporalSpan:
        """Construye un lapso a partir de los años-espejo enteros.

        Un año ``None`` degrada su extremo a precisión ``UNKNOWN`` (no se puede
        afirmar ``EXACT`` sin año)."""
        start = EventTemporality(
            year=birth_year,
            precision=precision if birth_year is not None else TemporalPrecision.UNKNOWN,
            notes=note,
        )
        end: EventTemporality | None = None
        if death_year is not None:
            end = EventTemporality(year=death_year, precision=precision, notes=note)
        return cls(start=start, end=end, ongoing=death_year is None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.to_dict() if self.start is not None else None,
            "end": self.end.to_dict() if self.end is not None else None,
            "ongoing": bool(self.ongoing),
            "nature": self.nature.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalSpan:
        if not isinstance(data, dict):
            data = {}
        raw_start = data.get("start")
        start = (
            EventTemporality.from_dict(raw_start)
            if isinstance(raw_start, dict)
            else EventTemporality()
        )
        raw_end = data.get("end")
        end = EventTemporality.from_dict(raw_end) if isinstance(raw_end, dict) else None
        ongoing = bool(data.get("ongoing", end is None))
        nature = _parse_nature(data.get("nature"))
        return cls(start=start, end=end, ongoing=ongoing, nature=nature)


def _parse_nature(value: Any) -> TemporalNature:
    """BETA1-J07: naturaleza temporal tolerante (default MORTAL)."""
    if isinstance(value, TemporalNature):
        return value
    if isinstance(value, str):
        try:
            return TemporalNature(value)
        except ValueError:
            pass
    return TemporalNature.MORTAL


__all__ = ["TemporalSpan"]
