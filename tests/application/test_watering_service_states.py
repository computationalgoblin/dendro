"""Estados derivados del riego e invalidación por vecindario (BETA2-FOCO-03).

Los timestamps se fijan explícitamente (sin sleeps ni relojes reales en las
comparaciones) para que la derivación sea determinista en cualquier máquina.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.domain.entity import CanonState, NarrativeEntity, NarrativeImportance
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.watering import WateringDiagnostic, WateringStatus

NOW = datetime.now(timezone.utc)


def _setup():
    project_service = ProjectService()
    project_service.create("Jardín")
    history_service = HistoryService(project_service)
    watering = WateringService(
        project_service, ai_job_service=None, history_service=history_service
    )
    return project_service, watering


def _entity(project_service, name, *, minutes_ago=60, **kwargs):
    project = project_service.active_project
    entity = NarrativeEntity(name=name, **kwargs)
    entity.updated_at = NOW - timedelta(minutes=minutes_ago)
    project.entities.append(entity)
    project.touch()
    return entity


def _relate(
    project_service,
    source,
    target,
    relation_type=RelationType.ESTA_RELACIONADO_CON,
    *,
    minutes_ago=60,
):
    project = project_service.active_project
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=relation_type
    )
    relation.updated_at = NOW - timedelta(minutes=minutes_ago)
    project.relations.append(relation)
    project.touch()
    return relation


def _water(watering, entity, *, minutes_ago=30, error=""):
    diagnostic = WateringDiagnostic(
        entity_id=entity.id,
        created_at=NOW - timedelta(minutes=minutes_ago),
        scores={} if error else {"arraigo": 50, "nutrida": 60, "iluminada": 40, "relevancia": 50},
        summary="" if error else "Lectura correcta.",
        error=error,
        resulting_status=(
            WateringStatus.FALTA_REGAR.value if error else WateringStatus.REGADA.value
        ),
    )
    result = watering.register_diagnostic(diagnostic)
    assert isinstance(result, Ok), getattr(result, "error", None)
    return diagnostic


def _edit(project_service, obj, *, minutes_ago=5):
    obj.updated_at = NOW - timedelta(minutes=minutes_ago)
    project_service.active_project.touch()


def _status(watering, entity):
    result = watering.status_of(entity.id)
    assert isinstance(result, Ok), getattr(result, "error", None)
    return result.value


@pytest.mark.application
class TestBasicStates:
    def test_never_watered_has_no_metrics(self):
        project_service, watering = _setup()
        entity = _entity(project_service, "Eldrin")

        report = _status(watering, entity)
        assert report.status == WateringStatus.FALTA_REGAR.value
        assert report.latest is None
        assert report.stale is False

    def test_watered_entity_is_regada(self):
        project_service, watering = _setup()
        entity = _entity(project_service, "Eldrin")
        _water(watering, entity)

        report = _status(watering, entity)
        assert report.status == WateringStatus.REGADA.value
        assert report.latest is not None
        assert report.latest.scores["nutrida"] == 60

    def test_rewater_regada_entity_is_not_blocked(self):
        # BETA2-FOCO-34: regar una entidad YA regada NO está bloqueado (sin
        # cooldown ni idempotencia). El segundo riego se registra y prevalece.
        project_service, watering = _setup()
        entity = _entity(project_service, "Eldrin")
        _water(watering, entity, minutes_ago=30)
        assert _status(watering, entity).status == WateringStatus.REGADA.value

        second = _water(watering, entity, minutes_ago=5)  # asserta Ok internamente
        report = _status(watering, entity)
        assert report.status == WateringStatus.REGADA.value
        assert report.latest is not None
        assert report.latest.created_at == second.created_at  # prevalece la nueva

    def test_editing_watered_entity_goes_stale_keeping_reading(self):
        project_service, watering = _setup()
        entity = _entity(project_service, "Eldrin")
        _water(watering, entity)
        _edit(project_service, entity)

        report = _status(watering, entity)
        assert report.status == WateringStatus.FALTA_REGAR.value
        assert report.stale is True
        assert report.latest is not None  # lectura antigua atenuada

    def test_unknown_entity_is_error(self):
        _, watering = _setup()
        assert isinstance(watering.status_of("nope"), Error)

    def test_ghost_has_no_cycle(self):
        project_service, watering = _setup()
        ghost = _entity(project_service, "¿Algo?", canon_state=CanonState.FANTASMA)

        report = _status(watering, ghost)
        assert report.status == WateringStatus.FALTA_REGAR.value
        assert report.latest is None
        # y no puede regarse ni secarse
        diagnostic = WateringDiagnostic(entity_id=ghost.id)
        assert isinstance(watering.register_diagnostic(diagnostic), Error)
        assert isinstance(watering.pause(ghost.id), Error)


@pytest.mark.application
class TestNeighborhoodInvalidation:
    """Caducidad por vecindario — RENEGOCIADA en BETA2-FIX-05 (G2-05).

    Regla vieja: editar la ficha de cualquier vecina (o de una de 2º grado de
    relevancia alta) caducaba un diagnóstico recién pagado. Era la TERCERA vía de
    invalidación del jardín —la que ningún tester identificó— y la que mantenía
    sedientas las 4 entidades regadas del mundo real del beta, incluida la única
    cuya página seguía `Regada`.

    Regla nueva: caduca solo el canon PROPIO de la entidad (su ficha, sus relaciones)
    y los cambios de FORMA del vecindario (altas/bajas/borrados), que invalidan el
    contexto enviado a la IA. El CONTENIDO de una vecina viaja ahora por el camino
    honesto: `NarrativeImpactService` marca `Falta regar` la PÁGINA de quien depende
    de ella y la unificación de frescura (WIKI-13) lo refleja en el jardín — a quien
    depende de verdad, no a todo el vecindario topológico.
    """

    def test_direct_neighbor_edit_no_longer_invalidates(self):
        # RENEGOCIADO (FIX-05): antes esto marcaba `falta_regar`. Ver docstring.
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        neighbor = _entity(project_service, "Vecina")
        _relate(project_service, center, neighbor)
        _water(watering, center)
        assert _status(watering, center).status == WateringStatus.REGADA.value

        _edit(project_service, neighbor)
        report = _status(watering, center)
        assert report.status == WateringStatus.REGADA.value
        assert report.stale is False

    def test_relation_edit_invalidates(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        neighbor = _entity(project_service, "Vecina")
        relation = _relate(project_service, center, neighbor)
        _water(watering, center)

        _edit(project_service, relation)
        assert _status(watering, center).status == WateringStatus.FALTA_REGAR.value

    def test_container_branch_edit_no_longer_invalidates(self):
        # RENEGOCIADO (FIX-05): la rama madre es una vecina; editar su ficha ya no
        # caduca la hoja. Editar la RELACIÓN de contención sí (test de arriba).
        project_service, watering = _setup()
        center = _entity(project_service, "Hoja")
        branch = _entity(project_service, "Rama madre")
        _relate(project_service, branch, center, RelationType.CONTIENE)
        _water(watering, center)

        _edit(project_service, branch)
        assert _status(watering, center).status == WateringStatus.REGADA.value

    def test_new_neighbor_after_watering_invalidates(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center)  # manifest registra vecindario vacío
        assert _status(watering, center).status == WateringStatus.REGADA.value

        newcomer = _entity(project_service, "Recién llegada", minutes_ago=90)
        _relate(project_service, center, newcomer, minutes_ago=90)
        # Timestamps antiguos a propósito: lo que dispara es la FIRMA de vecindario.
        assert _status(watering, center).status == WateringStatus.FALTA_REGAR.value

    def test_deleted_neighbor_invalidates(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        neighbor = _entity(project_service, "Efímera")
        _relate(project_service, center, neighbor)
        _water(watering, center)

        project = project_service.active_project
        project.entities.remove(neighbor)
        project.touch()
        assert _status(watering, center).status == WateringStatus.FALTA_REGAR.value

    def test_second_degree_edits_no_longer_invalidate(self):
        # RENEGOCIADO (FIX-05): ni la vecina de 2º grado modesta ni la crítica
        # caducan ya un diagnóstico fresco. Con 2º grado abierto, en un mundo real
        # de 30 fichas y 37 relaciones casi cualquier edición secaba casi todo.
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        bridge = _entity(project_service, "Puente")
        modest = _entity(
            project_service, "Secundaria", narrative_importance=NarrativeImportance.MEDIO
        )
        critical = _entity(
            project_service, "Crítica", narrative_importance=NarrativeImportance.CRITICO
        )
        _relate(project_service, center, bridge)
        _relate(project_service, bridge, modest)
        _relate(project_service, bridge, critical)
        _water(watering, center)
        assert _status(watering, center).status == WateringStatus.REGADA.value

        _edit(project_service, modest)
        assert _status(watering, center).status == WateringStatus.REGADA.value

        _edit(project_service, critical)
        assert _status(watering, center).status == WateringStatus.REGADA.value

    def test_own_edit_still_invalidates_after_the_renegotiation(self):
        # La mitad que NO se relaja: el canon PROPIO sigue caducando el diagnóstico.
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        neighbor = _entity(project_service, "Vecina")
        _relate(project_service, center, neighbor)
        _water(watering, center)
        assert _status(watering, center).status == WateringStatus.REGADA.value

        _edit(project_service, center)
        assert _status(watering, center).status == WateringStatus.FALTA_REGAR.value


@pytest.mark.application
class TestPauseResume:
    def test_paused_entity_never_invalidates(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        neighbor = _entity(project_service, "Vecina")
        _relate(project_service, center, neighbor)
        _water(watering, center)

        assert isinstance(watering.pause(center.id), Ok)
        assert _status(watering, center).status == WateringStatus.SECADA.value

        _edit(project_service, center)
        _edit(project_service, neighbor)
        report = _status(watering, center)
        assert report.status == WateringStatus.SECADA.value
        assert report.latest is not None  # lectura conservada/silenciada

    def test_pause_is_idempotent_and_needs_no_ai(self):
        project_service, watering = _setup()
        assert watering.ai_job_service is None  # todo el ciclo funciona sin IA
        center = _entity(project_service, "Centro")
        assert isinstance(watering.pause(center.id), Ok)
        assert isinstance(watering.pause(center.id), Ok)
        paused = project_service.active_project.watering_paused_entity_ids
        assert paused.count(center.id) == 1

    def test_resume_returns_to_falta_regar(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center)
        watering.pause(center.id)

        assert isinstance(watering.resume(center.id), Ok)
        report = _status(watering, center)
        # Contrato de producto: cultivar SIEMPRE vuelve como Falta regar.
        assert report.status == WateringStatus.FALTA_REGAR.value
        assert report.stale is True
        assert report.latest is not None

    def test_resume_without_pause_is_error(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        assert isinstance(watering.resume(center.id), Error)

    def test_pause_and_resume_record_history(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        watering.pause(center.id)
        watering.resume(center.id)
        _water(watering, center)

        events = [entry.event_type.value for entry in project_service.active_project.history]
        assert "secado_entidad" in events
        assert "cultivo_entidad" in events
        assert "riego_entidad" in events


@pytest.mark.application
class TestFailuresAndHistory:
    def test_failure_leaves_falta_regar_with_traceable_error(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center, minutes_ago=30)
        _water(watering, center, minutes_ago=10, error="timeout del proveedor")

        report = _status(watering, center)
        assert report.status == WateringStatus.FALTA_REGAR.value
        assert report.last_error == "timeout del proveedor"
        assert report.stale is True  # conserva la lectura buena anterior
        assert report.latest is not None and not report.latest.error

    def test_success_after_failure_recovers(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center, minutes_ago=30, error="fallo inicial")
        _water(watering, center, minutes_ago=10)

        report = _status(watering, center)
        assert report.status == WateringStatus.REGADA.value
        assert report.last_error == ""

    def test_history_for_returns_newest_first(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center, minutes_ago=30)
        _water(watering, center, minutes_ago=10, error="boom")

        result = watering.history_for(center.id)
        assert isinstance(result, Ok)
        entries = result.value
        assert len(entries) == 2
        assert entries[0].error == "boom"
        assert entries[1].error == ""


@pytest.mark.application
class TestCacheAndBatchStatuses:
    def test_statuses_for_all_and_subset(self):
        project_service, watering = _setup()
        watered = _entity(project_service, "Regada")
        pending = _entity(project_service, "Pendiente")
        _water(watering, watered)

        all_result = watering.statuses_for()
        assert isinstance(all_result, Ok)
        assert all_result.value[watered.id].status == WateringStatus.REGADA.value
        assert all_result.value[pending.id].status == WateringStatus.FALTA_REGAR.value

        subset = watering.statuses_for([watered.id, "desconocida"])
        assert isinstance(subset, Ok)
        assert set(subset.value.keys()) == {watered.id}

    def test_cache_refreshes_on_project_revision(self):
        project_service, watering = _setup()
        center = _entity(project_service, "Centro")
        _water(watering, center)
        assert _status(watering, center).status == WateringStatus.REGADA.value

        _edit(project_service, center)  # touch() del proyecto invalida la caché
        assert _status(watering, center).status == WateringStatus.FALTA_REGAR.value
