"""BETA2-MEM-05: servicio IA de actualizacion de Memoria (con fake LLM)."""

import json
from dataclasses import dataclass, field

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.memory_ai_service import MemoryAIService
from packages.application.memory_payload import normalize_memory_payload
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryIssueKind,
    MemoryTargetKind,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider

_VALID = {
    "resumen_editorial": "Ana es la reina exiliada que planea volver.",
    "estado_actual": "En el exilio, reuniendo aliados.",
    "notas_causales": ["Su exilio detona la guerra civil"],
    "issues": [
        {
            "kind": "contradiccion",
            "texto": "Muere en el capitulo 3 pero aparece viva despues",
            "anclado_a": [{"ref_kind": "milestone", "ref_id": "h1"}],
        }
    ],
    "citations": [{"ref_kind": "entity", "ref_id": "e2", "nota": "aliado"}],
}


class _FakeProvider(AIProvider):
    def __init__(self, *, payload=None, raw_text=None, error=None):
        self.payload = payload if payload is not None else dict(_VALID)
        self.raw_text = raw_text
        self.error = error
        self.calls = []

    @property
    def provider_name(self):
        return "fake_memory"

    def chat(self, system_prompt, user_message, timeout=None):
        self.calls.append((system_prompt, user_message))
        if self.error:
            return None, self.error
        if self.raw_text is not None:
            return self.raw_text, None
        return json.dumps(self.payload, ensure_ascii=False), None


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _setup(provider=None):
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    p.entities.append(NarrativeEntity(id="e2", name="Beto"))
    p.touch()
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    aijob = AIJobService(provider=provider or _FakeProvider(), project_provider=lambda: ps.active_project)
    svc = MemoryAIService(ps, aijob, memory_service=mem)
    return svc, mem, ps


# ── normalizador ─────────────────────────────────────────────────────────────


@pytest.mark.application
def test_normalize_valid_payload():
    result = normalize_memory_payload(dict(_VALID))
    assert isinstance(result, Ok)
    data = result.value
    assert data["resumen_editorial"].startswith("Ana")
    assert data["issues"][0]["kind"] == "contradiccion"
    assert data["citations"][0]["ref_id"] == "e2"


@pytest.mark.application
def test_normalize_rejects_missing_summary():
    assert isinstance(normalize_memory_payload({"estado_actual": "x"}), Error)
    assert isinstance(normalize_memory_payload("no-json"), Error)


@pytest.mark.application
def test_normalize_drops_malformed_issues_and_citations():
    data = normalize_memory_payload(
        {
            "resumen_editorial": "ok",
            "issues": [{"texto": ""}, "basura", {"kind": "raro", "texto": "vale"}],
            "citations": [{"ref_id": ""}, {"ref_id": "e9", "ref_kind": "milestone"}],
        }
    ).value
    assert len(data["issues"]) == 1
    assert data["issues"][0]["kind"] == "contradiccion"  # kind invalido -> default
    assert len(data["citations"]) == 1
    assert data["citations"][0]["ref_id"] == "e9"


# ── servicio: regar auto-aplica ────────────────────────────────────────────────


@pytest.mark.application
def test_regar_auto_applies_memory():
    svc, mem, _ = _setup()
    result = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")
    assert isinstance(result, Ok)
    assert result.value["applied"] is True
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block.freshness == MemoryFreshness.REGADA
    assert block.resumen_editorial.startswith("Ana")
    assert block.issues[0].kind == MemoryIssueKind.CONTRADICCION
    assert block.citations[0].ref_id == "e2"


@pytest.mark.application
def test_regar_clears_falta_regar():
    svc, mem, _ = _setup()
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="viejo")
    mem.mark_falta_regar(MemoryTargetKind.ENTITY, "e1")
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.freshness == MemoryFreshness.FALTA_REGAR
    svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.freshness == MemoryFreshness.REGADA


# ── servicio: regen propone diff sobre Memoria existente ───────────────────────


@pytest.mark.application
def test_regen_stages_proposal_when_memory_exists():
    svc, mem, _ = _setup()
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="version antigua")
    result = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regen")
    assert isinstance(result, Ok)
    assert result.value["applied"] is False
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    # NO se ha aplicado: el contenido sigue siendo el antiguo, pero hay propuesta.
    assert block.resumen_editorial == "version antigua"
    assert block.pending_revision is not None
    assert block.pending_revision.after["resumen_editorial"].startswith("Ana")


@pytest.mark.application
def test_regen_generates_directly_when_no_memory():
    svc, mem, _ = _setup()
    result = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regen")
    assert result.value["applied"] is True
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial.startswith("Ana")


# ── fallos limpios ─────────────────────────────────────────────────────────────


@pytest.mark.application
def test_invalid_ai_output_is_rejected():
    svc, mem, _ = _setup(provider=_FakeProvider(payload={"estado_actual": "sin resumen"}))
    result = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")
    assert isinstance(result, Error)
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value is None  # no se guardo basura


@pytest.mark.application
def test_unconfigured_provider_fails_clearly():
    # AIJobService sin proveedor real (simulated) -> provider_unconfigured True.
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    ps = _FakeProjectService(active_project=p)
    aijob = AIJobService(project_provider=lambda: ps.active_project)
    svc = MemoryAIService(ps, aijob)
    result = svc.update_memory(MemoryTargetKind.ENTITY, "e1", mode="regar")
    assert isinstance(result, Error)
    assert "IA" in result.error


@pytest.mark.application
def test_no_active_project_errors():
    aijob = AIJobService(provider=_FakeProvider(), project_provider=lambda: None)
    svc = MemoryAIService(_FakeProjectService(active_project=None), aijob)
    assert isinstance(svc.update_memory(MemoryTargetKind.ENTITY, "e1"), Error)
