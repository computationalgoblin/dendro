"""BETA2-WIKI-13b: la Memoria recibe la identidad TEMPORAL de la entidad.

Antes `_build_context` solo daba nombre/breve/desarrollo + relaciones + backlinks: la Memoria
era temporalmente ciega y no podía registrar en qué hitos participó la entidad (parte de quién
es). Ahora se le añade el LAPSO y los HITOS (reutilizando `classify_milestones`).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.application.memory_ai_service import MemoryAIService
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.project import Project


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _project():
    p = Project(id="p", name="P")
    ana = NarrativeEntity(id="ana", name="Ana", birth_year=10, death_year=45)
    p.entities.append(ana)
    p.entities.append(NarrativeEntity(id="beto", name="Beto"))
    p.causal_milestones.append(
        CausalMilestone(
            id="m1", title="Coronación", year=5,
            status=CausalMilestoneStatus.CANDIDATE, affected_entity_ids=["ana"],
        )
    )
    p.causal_milestones.append(
        CausalMilestone(
            id="m2", title="Exilio", year=40,
            status=CausalMilestoneStatus.CANDIDATE, affected_entity_ids=["ana"],
        )
    )
    return p


def _service(project):
    return MemoryAIService(_FakeProjectService(active_project=project), ai_job_service=None)


@pytest.mark.application
def test_temporal_lines_include_lapso_and_hitos():
    proj = _project()
    lines = MemoryAIService._entity_temporal_lines(proj, "ana")
    joined = "\n".join(lines)
    # BETA-FIX-03: los años viajan etiquetados («año N», con era si la hay).
    assert "LAPSO: año 10 → año 45" in joined
    # Año ≤ nacimiento ⇒ raíz (fundacional); posterior ⇒ brote.
    assert "[raíz] Coronación (año 5)" in joined
    assert "[brote] Exilio (año 40)" in joined


@pytest.mark.application
def test_build_context_registers_temporal_identity():
    proj = _project()
    ctx = _service(proj)._build_context(proj, MemoryTargetKind.ENTITY, "ana", "")
    assert "LAPSO:" in ctx
    assert "HITOS:" in ctx
    assert "Coronación" in ctx and "Exilio" in ctx


@pytest.mark.application
def test_entity_without_dates_or_milestones_has_no_temporal_lines():
    proj = _project()
    # Beto no tiene lapso ni participa en hitos.
    assert MemoryAIService._entity_temporal_lines(proj, "beto") == []


@pytest.mark.application
def test_temporal_lines_are_best_effort_on_bad_project():
    # proj sin causal_milestones ni entity_by_id (duck-typed) → no revienta.
    assert MemoryAIService._entity_temporal_lines(object(), "x") == []
