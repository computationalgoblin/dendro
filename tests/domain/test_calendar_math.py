"""BETA2-CAL-01 — Aritmética pura del calendario sintético.

Verifica días-por-año, día absoluto desde el origen (con meses de distinta longitud),
día de la semana real (con ancla y semanas no gregorianas), numeración regnal y el
roundtrip de ``CalendarConfig`` desde/hacia ``metadata`` (formas nueva y legacy).
"""

from __future__ import annotations

import pytest

from packages.domain.calendar_math import (
    CalendarConfig,
    days_per_year,
    days_since_origin,
    weekday_index,
)

MONTHS_3 = [("Enero", 31), ("Febrero", 28), ("Marzo", 31)]
WEEK_7 = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]


# ── Funciones puras ──────────────────────────────────────────────────────────


def test_days_per_year_is_sum_of_month_lengths():
    assert days_per_year([31, 28, 31]) == 90
    assert days_per_year([]) == 0


def test_days_since_origin_is_zero_at_calendar_origin():
    # era[0], año 1, mes 1 (index 0), día 1 → día absoluto 0.
    assert days_since_origin(0, 1, 0, 1, [31, 28, 31]) == 0


def test_days_since_origin_respects_unequal_month_lengths():
    lengths = [31, 28, 31]
    # 1 de Febrero (index 1) = 31 días de Enero antes.
    assert days_since_origin(0, 1, 1, 1, lengths) == 31
    # 1 de Marzo (index 2) = 31 + 28.
    assert days_since_origin(0, 1, 2, 1, lengths) == 59
    # 5 de Enero = 4 días después del origen.
    assert days_since_origin(0, 1, 0, 5, lengths) == 4


def test_days_since_origin_regnal_year_and_era_offset():
    lengths = [31, 28, 31]  # 90 días/año
    # Año 2 dentro de la misma era: un año completo antes.
    assert days_since_origin(0, 2, 0, 1, lengths) == 90
    # Era que empieza en el año absoluto 3 (duraciones previas = 3), su año 1.
    assert days_since_origin(3, 1, 0, 1, lengths) == 270


def test_weekday_index_wraps_and_uses_anchor():
    assert weekday_index(0, 0, 7) == 0
    assert weekday_index(31, 0, 7) == 3
    assert weekday_index(0, 2, 7) == 2  # ancla desplaza el origen
    # Semana no gregoriana de 5 días.
    assert weekday_index(5, 0, 5) == 0


def test_weekday_index_requires_positive_week_len():
    with pytest.raises(ValueError):
        weekday_index(3, 0, 0)


# ── CalendarConfig: día de la semana real ────────────────────────────────────


def test_weekday_name_at_origin_with_anchor_monday():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=0)
    assert cfg.weekday_name(0, 1, "Enero", 1) == "Lun"


def test_weekday_name_february_since_28_is_multiple_of_week():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=0)
    # 31 % 7 == 3 → Febrero 1 = Jueves; y como Febrero dura 28 (= 4 semanas),
    # Marzo 1 cae en el mismo día de la semana.
    assert cfg.weekday_name(0, 1, "Febrero", 1) == "Jue"
    assert cfg.weekday_name(0, 1, "Marzo", 1) == "Jue"


def test_weekday_name_across_eras():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=0)
    # Era que empieza en el año absoluto 3: 270 días → 270 % 7 == 4 → Viernes.
    assert cfg.weekday_name(3, 1, "Enero", 1) == "Vie"


def test_weekday_name_honours_anchor():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=2)
    assert cfg.weekday_name(0, 1, "Enero", 1) == "Mie"


def test_weekday_name_none_without_week():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=[], week_anchor=0)
    assert cfg.supports_exact_dates() is False
    assert cfg.weekday_name(0, 1, "Enero", 1) is None


def test_weekday_name_none_for_unknown_month():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=0)
    assert cfg.weekday_name(0, 1, "MesInexistente", 1) is None


# ── CalendarConfig: roundtrip y formatos ─────────────────────────────────────


def test_from_metadata_new_shape_under_calendar_key():
    meta = {
        "calendar": {
            "months": [{"name": "Enero", "length": 31}, {"name": "Febrero", "length": 28}],
            "weekdays": ["A", "B", "C"],
            "week_anchor": 5,  # se normaliza mod 3
        }
    }
    cfg = CalendarConfig.from_metadata(meta)
    assert cfg.months == [("Enero", 31), ("Febrero", 28)]
    assert cfg.weekdays == ["A", "B", "C"]
    assert cfg.week_anchor == 2


def test_from_metadata_legacy_blob_with_month_lengths_dict():
    meta = {
        "months": ["Enero", "Febrero"],
        "month_lengths": {"Enero": 31, "Febrero": 28},
        "weekdays": ["Lun", "Mar"],
        "days_per_month": 30,
    }
    cfg = CalendarConfig.from_metadata(meta)
    assert cfg.months == [("Enero", 31), ("Febrero", 28)]
    assert cfg.weekdays == ["Lun", "Mar"]
    assert cfg.week_anchor == 0


def test_from_metadata_legacy_month_lengths_as_text_and_default():
    meta = {
        "months": ["Enero", "Febrero", "Marzo"],
        "month_lengths": "Enero: 31\nFebrero: 28",  # Marzo cae al defecto
        "days_per_month": 30,
    }
    cfg = CalendarConfig.from_metadata(meta)
    assert cfg.months == [("Enero", 31), ("Febrero", 28), ("Marzo", 30)]


def test_calendar_config_roundtrips_through_metadata():
    cfg = CalendarConfig(months=MONTHS_3, weekdays=WEEK_7, week_anchor=3)
    back = CalendarConfig.from_metadata(cfg.to_metadata())
    assert back.months == cfg.months
    assert back.weekdays == cfg.weekdays
    assert back.week_anchor == cfg.week_anchor


def test_empty_metadata_is_only_eras_calendar():
    cfg = CalendarConfig.from_metadata({})
    assert cfg.has_months() is False
    assert cfg.has_week() is False
    assert cfg.supports_exact_dates() is False
    assert cfg.days_per_year() == 0
