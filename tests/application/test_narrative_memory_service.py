"""BETA2-MEM-02: NarrativeMemoryService (CRUD + frescura + propuestas + historia).

Servicio de aplicación sin IA ni UI. Los tests usan un project_service mínimo con
``active_project`` (patrón HistoryService) y un HistoryService real para verificar
la trazabilidad. La app debe funcionar también sin IA configurada.
"""

from dataclasses import dataclass

import pytest

from packages.application.history_service import HistoryService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryOrigin,
    MemoryTargetKind,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.domain.source_history import HistoryEventType


@dataclass
class _FakeProjectService:
    active_project: Project | None = None


def _service(with_history: bool = True):
    ps = _FakeProjectService(active_project=Project(id="p", name="P"))
    history = HistoryService(ps) if with_history else None
    return NarrativeMemoryService(ps, history), ps


@pytest.mark.application
def test_no_active_project_returns_error():
    svc = NarrativeMemoryService(_FakeProjectService(active_project=None))
    result = svc.upsert_memory(MemoryTargetKind.PROJECT)
    assert isinstance(result, Error)
    assert "proyecto activo" in result.error


@pytest.mark.application
def test_upsert_creates_block_regada_and_lists():
    svc, ps = _service()
    result = svc.upsert_memory(
        MemoryTargetKind.ENTITY, "e1", resumen_editorial="Vive en el exilio."
    )
    assert isinstance(result, Ok)
    block = result.value
    assert block.freshness == MemoryFreshness.REGADA
    assert block.resumen_editorial == "Vive en el exilio."
    assert ps.active_project.narrative_memories == [block]
    listed = svc.list_memories(MemoryTargetKind.ENTITY)
    assert isinstance(listed, Ok)
    assert listed.value == [block]


@pytest.mark.application
def test_upsert_updates_only_provided_fields():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="A", estado_actual="B")
    updated = svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", estado_actual="C").value
    assert updated.resumen_editorial == "A"  # no se pisa lo no aportado
    assert updated.estado_actual == "C"
    # sigue siendo el mismo bloque (no duplica)
    assert len(_service_project(svc).narrative_memories) == 1


def _service_project(svc: NarrativeMemoryService) -> Project:
    return svc.project_service.active_project


@pytest.mark.application
def test_context_distinguishes_blocks():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="general")
    svc.upsert_memory(
        MemoryTargetKind.ENTITY, "e1", context="guerra", resumen_editorial="en guerra"
    )
    assert len(_service_project(svc).narrative_memories) == 2
    general = svc.get_memory(MemoryTargetKind.ENTITY, "e1").value
    contextual = svc.get_memory(MemoryTargetKind.ENTITY, "e1", "guerra").value
    assert general.resumen_editorial == "general"
    assert contextual.resumen_editorial == "en guerra"


@pytest.mark.application
def test_get_memory_absent_returns_none():
    svc, _ = _service()
    assert svc.get_memory(MemoryTargetKind.ENTITY, "nope").value is None


@pytest.mark.application
def test_mark_falta_regar_preserves_content():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="contenido valioso")
    result = svc.mark_falta_regar(MemoryTargetKind.ENTITY, "e1", causa="cambió una relación")
    assert isinstance(result, Ok)
    block = result.value
    assert block.freshness == MemoryFreshness.FALTA_REGAR
    assert block.resumen_editorial == "contenido valioso"  # criterio 4: no borra


@pytest.mark.application
def test_mark_falta_regar_creates_empty_when_missing():
    svc, _ = _service()
    block = svc.mark_falta_regar(MemoryTargetKind.ENTITY, "sinmemoria").value
    assert block.freshness == MemoryFreshness.FALTA_REGAR
    assert block.resumen_editorial == ""


@pytest.mark.application
def test_mark_falta_regar_no_create_returns_none():
    svc, _ = _service()
    result = svc.mark_falta_regar(MemoryTargetKind.ENTITY, "x", create_if_missing=False)
    assert isinstance(result, Ok)
    assert result.value is None


@pytest.mark.application
def test_set_freshness_secada():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.PROJECT)
    block = svc.set_freshness(MemoryTargetKind.PROJECT, freshness=MemoryFreshness.SECADA).value
    assert block.freshness == MemoryFreshness.SECADA


@pytest.mark.application
def test_delete_memory():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1")
    assert svc.delete_memory(MemoryTargetKind.ENTITY, "e1").value is True
    assert svc.get_memory(MemoryTargetKind.ENTITY, "e1").value is None
    # borrar de nuevo: no existe
    assert svc.delete_memory(MemoryTargetKind.ENTITY, "e1").value is False


@pytest.mark.application
def test_stage_and_apply_revision_proposal():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="viejo")
    staged = svc.stage_revision_proposal(
        MemoryTargetKind.ENTITY, "e1", after={"resumen_editorial": "nuevo"}, motivo="regar"
    )
    assert isinstance(staged, Ok)
    proposal = staged.value
    assert proposal.before == {"resumen_editorial": "viejo", "estado_actual": "",
                               "cuerpo": "", "issues": [], "notas_causales": [],
                               "dependencias": [], "citations": [],
                               "wikilinks": [], "tags": []}
    # aún NO se ha aplicado el cambio
    assert svc.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial == "viejo"
    assert svc.get_memory(MemoryTargetKind.ENTITY, "e1").value.pending_revision is not None

    applied = svc.apply_revision_proposal(MemoryTargetKind.ENTITY, "e1")
    assert isinstance(applied, Ok)
    block = applied.value
    assert block.resumen_editorial == "nuevo"
    assert block.pending_revision is None
    assert block.freshness == MemoryFreshness.REGADA


@pytest.mark.application
def test_apply_replaces_structured_issues():
    svc, _ = _service()
    svc.upsert_memory(
        MemoryTargetKind.ENTITY,
        "e1",
        issues=[MemoryIssue(kind=MemoryIssueKind.HUECO, texto="viejo hueco")],
    )
    new_issue = MemoryIssue(kind=MemoryIssueKind.CONTRADICCION, texto="nueva contradicción")
    svc.stage_revision_proposal(
        MemoryTargetKind.ENTITY, "e1", after={"issues": [new_issue.to_dict()]}
    )
    block = svc.apply_revision_proposal(MemoryTargetKind.ENTITY, "e1").value
    assert len(block.issues) == 1
    assert block.issues[0].kind == MemoryIssueKind.CONTRADICCION
    assert block.issues[0].texto == "nueva contradicción"


@pytest.mark.application
def test_discard_revision_proposal():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="original")
    svc.stage_revision_proposal(
        MemoryTargetKind.ENTITY, "e1", after={"resumen_editorial": "descartado"}
    )
    discarded = svc.discard_revision_proposal(MemoryTargetKind.ENTITY, "e1")
    assert isinstance(discarded, Ok)
    block = discarded.value
    assert block.pending_revision is None
    assert block.resumen_editorial == "original"  # sin cambios de contenido


@pytest.mark.application
def test_apply_without_pending_proposal_errors():
    svc, _ = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1")
    result = svc.apply_revision_proposal(MemoryTargetKind.ENTITY, "e1")
    assert isinstance(result, Error)


@pytest.mark.application
def test_history_is_recorded_for_entity_memory():
    svc, ps = _service()
    svc.upsert_memory(
        MemoryTargetKind.ENTITY, "e1", resumen_editorial="x", origin=MemoryOrigin.RIEGO
    )
    entries = ps.active_project.history
    assert any(e.event_type == HistoryEventType.MEMORIA_ACTUALIZADA for e in entries)
    entry = next(e for e in entries if e.event_type == HistoryEventType.MEMORIA_ACTUALIZADA)
    assert entry.affected_entity_id == "e1"
    assert entry.metadata.get("target_kind") == "entity"


@pytest.mark.application
def test_falta_regar_records_history_event():
    svc, ps = _service()
    svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="x")
    svc.mark_falta_regar(MemoryTargetKind.ENTITY, "e1", causa="cambio")
    assert any(
        e.event_type == HistoryEventType.MEMORIA_FALTA_REGAR for e in ps.active_project.history
    )


@pytest.mark.application
def test_works_without_history_service():
    """Smoke sin IA/servicios opcionales: el servicio funciona con history=None."""
    svc, _ = _service(with_history=False)
    result = svc.upsert_memory(MemoryTargetKind.PROJECT, resumen_editorial="global")
    assert isinstance(result, Ok)
    assert result.value.resumen_editorial == "global"
