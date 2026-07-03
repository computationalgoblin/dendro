"""Riego en lote: ámbitos, parciales persistentes y fallos trazables (BETA2-FOCO-07)."""

from __future__ import annotations

import json

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.watering import WateringStatus
from packages.infrastructure.ai_provider import AIProvider

_PAYLOAD = {
    "scores": {"arraigo": 60, "nutrida": 60, "iluminada": 60},
    "summary": "Lectura de lote.",
    "metric_explanations": {},
    "risks": [],
}


class BatchProvider(AIProvider):
    provider_name = "fake_batch"
    model = "fake-model-1"

    def __init__(self, fail_marker: str = ""):
        self.fail_marker = fail_marker
        self.calls: list[str] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append(user_message)
        if self.fail_marker and self.fail_marker in user_message:
            return None, "timeout simulado del proveedor"
        return json.dumps(_PAYLOAD, ensure_ascii=False), None


def _setup(fail_marker: str = ""):
    project_service = ProjectService()
    project_service.create("Lote")
    provider = BatchProvider(fail_marker)
    ai_service = AIJobService(
        provider=provider, project_provider=lambda: project_service.active_project
    )
    watering = WateringService(
        project_service, ai_job_service=ai_service, history_service=HistoryService(project_service)
    )
    return project_service, watering, provider


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _contain(project_service, parent, child):
    relation = NarrativeRelation(
        source_id=parent.id, target_id=child.id, relation_type=RelationType.CONTIENE
    )
    project_service.active_project.relations.append(relation)
    project_service.active_project.touch()
    return relation


@pytest.mark.application
class TestBatchSteps:
    def test_partial_results_with_traceable_failure(self):
        project_service, watering, _ = _setup(fail_marker="Fallona")
        alpha = _entity(project_service, "Alfa")
        failing = _entity(project_service, "Fallona")
        zeta = _entity(project_service, "Zeta")

        scope = watering.entities_in_scope({"selection": [alpha.id, failing.id, zeta.id]})
        assert isinstance(scope, Ok)
        outcomes = [watering.water_batch_step(entity_id) for entity_id in scope.value]

        oks = [r for r in outcomes if isinstance(r, Ok)]
        errors = [r for r in outcomes if isinstance(r, Error)]
        assert len(oks) == 2 and len(errors) == 1

        project = project_service.active_project
        assert len(project.watering_diagnostics) == 3  # 2 éxitos + 1 fallo trazable
        assert all(d.origin == "batch" for d in project.watering_diagnostics)

        failing_report = watering.status_of(failing.id).value
        assert failing_report.status == WateringStatus.FALTA_REGAR.value
        assert "timeout" in failing_report.last_error
        assert watering.status_of(alpha.id).value.status == WateringStatus.REGADA.value
        assert watering.status_of(zeta.id).value.status == WateringStatus.REGADA.value

    def test_interruption_between_steps_keeps_partials(self):
        project_service, watering, _ = _setup()
        first = _entity(project_service, "Primera")
        _entity(project_service, "Segunda")

        scope = watering.entities_in_scope({"graph": True}).value
        # El host cancela ENTRE pasos: solo se ejecuta el primero.
        assert isinstance(watering.water_batch_step(scope[0]), Ok)
        project = project_service.active_project
        assert len(project.watering_diagnostics) == 1
        assert watering.status_of(first.id).value.status == WateringStatus.REGADA.value


@pytest.mark.application
class TestScopes:
    def test_graph_scope_excludes_ineligibles(self):
        project_service, watering, _ = _setup()
        keep = _entity(project_service, "Activa")
        _entity(project_service, "¿Fantasma?", canon_state=CanonState.FANTASMA)
        _entity(project_service, "Archivada", canon_state=CanonState.ARCHIVADO)
        paused = _entity(project_service, "Secada")
        watering.pause(paused.id)

        scope = watering.entities_in_scope({"graph": True})
        assert isinstance(scope, Ok)
        assert scope.value == [keep.id]

    def test_selection_scope_orders_and_skips_unknown(self):
        project_service, watering, _ = _setup()
        zeta = _entity(project_service, "Zeta")
        alfa = _entity(project_service, "Alfa")
        scope = watering.entities_in_scope({"selection": [zeta.id, "nope", alfa.id]})
        assert isinstance(scope, Ok)
        assert scope.value == [alfa.id, zeta.id]

    def test_ring_scope_uses_direct_membership(self):
        project_service, watering, _ = _setup()
        inside = _entity(project_service, "Dentro", layer_ids=["layer_x"])
        _entity(project_service, "Fuera", layer_ids=["layer_y"])
        scope = watering.entities_in_scope({"ring_id": "layer_x"})
        assert isinstance(scope, Ok)
        assert scope.value == [inside.id]

    def test_branch_scope_is_recursive_and_filters(self):
        project_service, watering, _ = _setup()
        branch = _entity(project_service, "Rama madre", entity_type="contenedor")
        child = _entity(project_service, "Hija")
        grandchild = _entity(project_service, "Nieta")
        ghost_member = _entity(project_service, "¿Miembro?", canon_state=CanonState.FANTASMA)
        outsider = _entity(project_service, "Ajena")
        _contain(project_service, branch, child)
        _contain(project_service, child, grandchild)
        _contain(project_service, branch, ghost_member)

        scope = watering.entities_in_scope({"branch_id": branch.id})
        assert isinstance(scope, Ok)
        assert set(scope.value) == {branch.id, child.id, grandchild.id}
        assert outsider.id not in scope.value

    def test_unknown_scope_is_error(self):
        _, watering, _ = _setup()
        assert isinstance(watering.entities_in_scope({}), Error)
        assert isinstance(watering.entities_in_scope({"branch_id": "nope"}), Error)
