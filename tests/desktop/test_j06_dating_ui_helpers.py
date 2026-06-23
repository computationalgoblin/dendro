"""BETA1-J06 — Helpers puros de UI de datación (badge + avisos), sin Qt."""

from __future__ import annotations

from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    dating_badge_label,
    temporal_warnings_text,
)
from packages.application.temporal_dating import PENDING_NOTE
from packages.domain.entity import NarrativeEntity
from packages.domain.temporal_models import (
    EventTemporality,
    TemporalNature,
    TemporalPrecision,
)
from packages.domain.temporal_span import TemporalSpan


class _Cand:
    def __init__(self, metadata):
        self.metadata = metadata


# ── Avisos de coherencia ──────────────────────────────────────────────────


def test_warnings_text_empty_when_none():
    assert temporal_warnings_text(_Cand({})) == ""
    assert temporal_warnings_text(_Cand(None)) == ""


def test_warnings_text_lists_messages():
    cand = _Cand(
        {"temporal_warnings": [{"code": "T04", "message": "Relación antes del origen"}]}
    )
    out = temporal_warnings_text(cand)
    assert "Avisos de coherencia temporal" in out
    assert "• Relación antes del origen" in out


# ── Badge de datación ─────────────────────────────────────────────────────


def test_badge_por_datar():
    e = NarrativeEntity(name="X")
    e.set_life_span(TemporalSpan(start=EventTemporality()))  # sin datar
    assert dating_badge_label(e) == "Por datar"


def test_badge_datado():
    e = NarrativeEntity(name="X")
    e.set_life_span(TemporalSpan.from_years(-40, 12))  # EXACT
    assert dating_badge_label(e) == "Datado"


def test_badge_sin_fundamentar_migrated():
    e = NarrativeEntity(name="X")
    e.set_life_span(
        TemporalSpan(
            start=EventTemporality(
                year=312, precision=TemporalPrecision.UNKNOWN,
                notes="no fundamentado (migración v27)",
            )
        )
    )
    assert dating_badge_label(e) == "Sin fundamentar"


def test_badge_aproximado():
    e = NarrativeEntity(name="X")
    e.set_life_span(
        TemporalSpan(start=EventTemporality(year=300, precision=TemporalPrecision.APPROXIMATE))
    )
    assert dating_badge_label(e) == "Aproximado"


def test_badge_reflects_temporal_nature():
    # BETA1-J07: la naturaleza manda sobre la precisión.
    eternal = NarrativeEntity(name="Ángel")
    eternal.set_life_span(
        TemporalSpan(start=EventTemporality(year=None), nature=TemporalNature.ETERNO)
    )
    assert dating_badge_label(eternal) == "Eterno"

    immortal = NarrativeEntity(name="Deidad")
    immortal.set_life_span(
        TemporalSpan(start=EventTemporality(year=100), nature=TemporalNature.INMORTAL)
    )
    assert dating_badge_label(immortal) == "Inmortal"

    atemporal = NarrativeEntity(name="Ley")
    atemporal.set_life_span(
        TemporalSpan(start=EventTemporality(), nature=TemporalNature.ATEMPORAL)
    )
    assert dating_badge_label(atemporal) == "Atemporal"


def test_pending_note_constant_used():
    # El badge 'Por datar' se apoya en el span sin datar; la nota pendiente es
    # la marca canónica de J04.
    assert PENDING_NOTE
