"""BETA-MULTIAGENT2-FIX-09 (§6): el paso del recorrido deja de mentirle a la IA.

`_rings_context` metía en el prompt un `causal_chain` construido sobre
`causal_child_hito_ids` —el campo que no escribía nadie—, así que el contexto
afirmaba que el hito no tenía consecuencias aunque tuviera quince episodios
colgando. Y esa llamada se cobra igual.
"""

from __future__ import annotations

import pytest

from packages.application.chronology_walk_service import ChronologyWalkService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.result import Ok


class _FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class _FakeJob:
    def __init__(self, result):
        self.id = "job_fake"
        self.result = result


class _FakeAIJobService:
    def __init__(self):
        self.calls: list[dict] = []

    def run_focused_job(self, job_type, prompt, *, context_scope=None, progress_callback=None):
        self.calls.append({"job_type": job_type, "prompt": prompt, "context": context_scope})
        return Ok(
            _FakeJob(
                {
                    "kind": "analysis",
                    "summary": "",
                    "report": "",
                    "candidates": [],
                    "open_questions": [],
                    "model_payload": {},
                }
            )
        )


def _project_abc() -> Project:
    """A → B → C declarados SOLO por el lado padre (como los mundos del beta)."""
    project = Project(id="p-fix09", name="Hilo")
    project.causal_milestones.extend(
        [
            CausalMilestone(id="A", title="Setup", year=100),
            CausalMilestone(id="B", title="Vuelta de tuerca", year=200,
                            causal_parent_hito_ids=["A"]),
            CausalMilestone(id="C", title="Payoff", year=300,
                            causal_parent_hito_ids=["B"]),
        ]
    )
    return project


@pytest.mark.application
def test_beta_m2fix09_rings_context_lleva_la_cadena_completa():
    project = _project_abc()
    svc = ChronologyWalkService(
        project_service=_FakeProjectService(project), ai_job_service=_FakeAIJobService()
    )

    rings = svc._rings_context(project, project.causal_milestones[0])

    assert [b["id"] for b in rings["causal_chain"]] == ["A", "B", "C"]
    # las consecuencias DIRECTAS también viajan derivadas, no desde el espejo vacío
    assert rings["causal_child_hito_ids"] == ["B"]


@pytest.mark.application
def test_beta_m2fix09_el_prompt_del_paso_recibe_la_cadena():
    """El contexto que se manda al proveedor (y se paga) trae los tres hitos."""
    project = _project_abc()
    ai = _FakeAIJobService()
    svc = ChronologyWalkService(
        project_service=_FakeProjectService(project), ai_job_service=ai
    )
    sesion = svc.start_walk("A")
    assert isinstance(sesion, Ok)

    svc.analyze_step(sesion.value.id)

    contexto = ai.calls[0]["context"]
    cadena = contexto["chrono_walk"]["rings"]["causal_chain"]
    assert [b["title"] for b in cadena] == ["Setup", "Vuelta de tuerca", "Payoff"]
