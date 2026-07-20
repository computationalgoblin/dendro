"""Cola de atención del riego (BETA2-JARDIN-03): orden y exclusiones."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from packages.application.watering_attention import thirsty_queue, waterable_queue

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _entity(entity_id: str, *, name: str = "", canon: str = "canonico", created=None):
    return SimpleNamespace(
        id=entity_id,
        name=name or entity_id,
        canon_state=SimpleNamespace(value=canon),
        created_at=created or _T0,
    )


def _report(status: str, *, diagnosed=None):
    latest = SimpleNamespace(created_at=diagnosed) if diagnosed is not None else None
    return SimpleNamespace(status=status, latest=latest, stale=False)


def _project(*entities):
    return SimpleNamespace(entities=list(entities))


class TestThirstyQueue:
    def test_oldest_first_mixing_diagnosed_and_never_watered(self):
        # 'vieja' se regó hace mucho (diagnóstico antiguo); 'nueva' nunca se
        # regó pero se creó después; 'reciente' tiene diagnóstico fresco.
        project = _project(
            _entity("nueva", created=_T0 + timedelta(days=5)),
            _entity("vieja"),
            _entity("reciente"),
        )
        reports = {
            "vieja": _report("falta_regar", diagnosed=_T0 + timedelta(days=1)),
            "nueva": _report("falta_regar"),
            "reciente": _report("falta_regar", diagnosed=_T0 + timedelta(days=9)),
        }
        assert thirsty_queue(project, reports) == ["vieja", "nueva", "reciente"]

    def test_only_falta_regar_counts(self):
        project = _project(_entity("a"), _entity("b"), _entity("c"))
        reports = {
            "a": _report("regada"),
            "b": _report("falta_regar"),
            "c": _report("secada"),
        }
        assert thirsty_queue(project, reports) == ["b"]

    def test_ghosts_and_archived_are_excluded(self):
        # WateringService reporta falta_regar para fantasmas: aquí se filtran.
        project = _project(
            _entity("g", canon="fantasma"),
            _entity("x", canon="archivado"),
            _entity("real"),
        )
        reports = {key: _report("falta_regar") for key in ("g", "x", "real")}
        assert thirsty_queue(project, reports) == ["real"]

    def test_tie_breaks_by_name_then_id_stable(self):
        project = _project(
            _entity("id2", name="Zeta"),
            _entity("id1", name="alfa"),
            _entity("id0", name="alfa"),
        )
        reports = {key: _report("falta_regar") for key in ("id0", "id1", "id2")}
        # Mismo timestamp → nombre (casefold) y luego id.
        assert thirsty_queue(project, reports) == ["id0", "id1", "id2"]

    def test_missing_report_or_project_is_safe(self):
        assert thirsty_queue(None, {}) == []
        project = _project(_entity("sin_report"))
        assert thirsty_queue(project, {}) == []

    def test_naive_timestamps_do_not_crash(self):
        project = _project(
            _entity("naive", created=datetime(2025, 1, 1)),
            _entity("aware"),
        )
        reports = {
            "naive": _report("falta_regar"),
            "aware": _report("falta_regar"),
        }
        assert thirsty_queue(project, reports) == ["naive", "aware"]


class TestWaterableQueue:
    def test_orders_falta_then_regada(self):
        # BETA2-FOCO-34: el badge no desaparece — regables = falta_regar (1º) + regada.
        project = _project(_entity("seca"), _entity("regada"), _entity("otra_seca"))
        reports = {
            "regada": _report("regada", diagnosed=_T0 + timedelta(days=1)),
            "seca": _report("falta_regar"),
            "otra_seca": _report("falta_regar", diagnosed=_T0 + timedelta(days=2)),
        }
        # Primero las sedientas (por antigüedad), luego las regadas.
        assert waterable_queue(project, reports) == ["seca", "otra_seca", "regada"]

    def test_excludes_secada_ghost_and_archived(self):
        project = _project(
            _entity("g", canon="fantasma"),
            _entity("arc", canon="archivado"),
            _entity("pausada"),
            _entity("viva"),
        )
        reports = {
            "g": _report("regada"),
            "arc": _report("regada"),
            "pausada": _report("secada"),
            "viva": _report("regada"),
        }
        assert waterable_queue(project, reports) == ["viva"]

    def test_missing_report_or_project_is_safe(self):
        assert waterable_queue(None, {}) == []
        assert waterable_queue(_project(_entity("x")), {}) == []
