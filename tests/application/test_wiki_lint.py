"""BETA2-WIKI-07: lint de la wiki (determinista + contradicciones IA single-shot)."""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.wiki_lint_service import WikiLintService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


@dataclass
class _FakeProjectService:
    active_project: Project = None


class _FakeProvider(AIProvider):
    def __init__(self, payload):
        self._payload = payload

    @property
    def provider_name(self):
        return "fake"

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        return json.dumps(self._payload, ensure_ascii=False), None


def _project():
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    return _FakeProjectService(active_project=p), p


@pytest.mark.application
def test_detects_orphan_page():
    ps, p = _project()
    p.narrative_memories.append(
        NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="ghost",
                        resumen_editorial="huérfana")
    )
    report = WikiLintService(ps).lint().value
    assert len(report.orphans) == 1
    assert report.orphans[0].target_id == "ghost"


@pytest.mark.application
def test_detects_broken_link():
    ps, p = _project()
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY, target_id="e1", resumen_editorial="Ana",
            wikilinks=[MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="e404")],
        )
    )
    report = WikiLintService(ps).lint().value
    assert len(report.broken_links) == 1
    assert "e404" in report.broken_links[0].detail


@pytest.mark.application
def test_detects_stale_page():
    ps, p = _project()
    p.narrative_memories.append(
        NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="e1",
                        resumen_editorial="Ana", freshness=MemoryFreshness.FALTA_REGAR)
    )
    report = WikiLintService(ps).lint().value
    assert len(report.stale) == 1


@pytest.mark.application
def test_detects_anchored_contradiction():
    ps, p = _project()
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY, target_id="e1", resumen_editorial="Ana",
            issues=[MemoryIssue(kind=MemoryIssueKind.CONTRADICCION, texto="vive y murió")],
        )
    )
    report = WikiLintService(ps).lint().value
    assert len(report.contradictions) == 1
    assert "vive y murió" in report.contradictions[0].detail


@pytest.mark.application
def test_clean_project_reports_no_issues():
    ps, p = _project()
    p.narrative_memories.append(
        NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="e1",
                        resumen_editorial="Ana", freshness=MemoryFreshness.REGADA)
    )
    report = WikiLintService(ps).lint().value
    assert report.is_clean()


@pytest.mark.application
def test_ai_contradictions_single_shot():
    ps, p = _project()
    p.entities.append(NarrativeEntity(id="e2", name="Beto"))
    for eid, txt in [("e1", "Ana está viva"), ("e2", "Ana murió en la guerra")]:
        p.narrative_memories.append(
            NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id=eid,
                            resumen_editorial=txt, freshness=MemoryFreshness.REGADA)
        )
    payload = {"contradicciones": [{"texto": "Ana viva vs muerta", "paginas": ["e1", "e2"]}]}
    aijob = AIJobService(provider=_FakeProvider(payload))
    res = WikiLintService(ps, ai_job_service=aijob).detect_ai_contradictions()
    assert isinstance(res, Ok)
    assert len(res.value) == 1
    assert "Ana viva vs muerta" in res.value[0].detail


@pytest.mark.application
def test_ai_contradictions_needs_provider():
    ps, p = _project()
    p.entities.append(NarrativeEntity(id="e2", name="Beto"))
    for eid in ("e1", "e2"):
        p.narrative_memories.append(
            NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id=eid,
                            resumen_editorial="x")
        )
    res = WikiLintService(ps, ai_job_service=AIJobService()).detect_ai_contradictions()
    assert isinstance(res, Error)


@pytest.mark.application
def test_ai_contradictions_noop_with_few_pages():
    ps, p = _project()
    aijob = AIJobService(provider=_FakeProvider({"contradicciones": []}))
    res = WikiLintService(ps, ai_job_service=aijob).detect_ai_contradictions()
    assert isinstance(res, Ok) and res.value == []
