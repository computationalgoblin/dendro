"""BETA2-WIKI-13: el estado de riego y la frescura de la página de Memoria se unifican.

El chip de riego (diagnóstico del jardín) y el chip de Memoria (página de wiki) compartían
vocabulario ("Regada"/"Falta regar") y podían contradecirse: regar una entidad RELACIONADA
marca la página como Falta regar (propagación causal) sin re-disparar el diagnóstico. Ahora
el estado de riego refleja también la frescura de la página: si la página está Falta regar,
el jardín también, y un solo Regar los revive. SECADA/FANTASMA siguen ganando.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.result import Ok
from packages.domain.watering import WateringDiagnostic, WateringStatus

NOW = datetime.now(timezone.utc)


def _setup(with_memory=True):
    ps = ProjectService()
    ps.create("Jardín")
    mem = NarrativeMemoryService(ps) if with_memory else None
    watering = WateringService(ps, ai_job_service=None, memory_service=mem)
    return ps, watering, mem


def _entity(ps, name="Corte"):
    e = NarrativeEntity(name=name)
    e.updated_at = NOW - timedelta(minutes=60)
    ps.active_project.entities.append(e)
    ps.active_project.touch()
    return e


def _water(watering, entity):
    diag = WateringDiagnostic(
        entity_id=entity.id,
        created_at=NOW - timedelta(minutes=30),
        scores={"arraigo": 50, "nutrida": 60, "iluminada": 40, "relevancia": 50},
        summary="Lectura correcta.",
        resulting_status=WateringStatus.REGADA.value,
    )
    assert isinstance(watering.register_diagnostic(diag), Ok)


@pytest.mark.application
def test_regada_stays_regada_without_stale_memory():
    ps, watering, _mem = _setup()
    e = _entity(ps)
    _water(watering, e)  # sin página de Memoria → SIN_MEMORIA, no degrada
    assert watering.status_of(e.id).value.status == WateringStatus.REGADA.value


@pytest.mark.application
def test_regada_downgrades_when_memory_page_falta_regar():
    ps, watering, mem = _setup()
    e = _entity(ps)
    _water(watering, e)
    # Simula la propagación: una relacionada regada marcó ESTA página Falta regar.
    assert isinstance(mem.mark_falta_regar(MemoryTargetKind.ENTITY, e.id), Ok)
    report = watering.status_of(e.id).value
    assert report.status == WateringStatus.FALTA_REGAR.value
    assert report.stale is True
    assert report.latest is not None  # conserva el diagnóstico previo


@pytest.mark.application
def test_no_memory_service_means_no_coupling():
    ps, watering, _ = _setup(with_memory=False)
    e = _entity(ps)
    _water(watering, e)
    assert watering.status_of(e.id).value.status == WateringStatus.REGADA.value


@pytest.mark.application
def test_secada_wins_over_stale_memory():
    ps, watering, mem = _setup()
    e = _entity(ps)
    _water(watering, e)
    assert isinstance(mem.mark_falta_regar(MemoryTargetKind.ENTITY, e.id), Ok)
    assert isinstance(watering.pause(e.id), Ok)  # Secar
    # Aunque la página esté Falta regar, Secada (fuera del ciclo) gana.
    assert watering.status_of(e.id).value.status == WateringStatus.SECADA.value
