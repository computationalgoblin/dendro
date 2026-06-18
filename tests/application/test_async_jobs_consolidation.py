"""Consolidation + determinism for the new command pipeline.

Locks two product decisions:
  * Every contextual action (menu / panel) runs through the SAME AIJobService
    the command bar uses, so all jobs share one registry / tray.
  * The command bar resolves intent from the two selectors verbatim — an
    explicit job type is never overridden by keyword classification.
"""
from __future__ import annotations

from packages.application.ai_context_actions import AIContextActionService
from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    CommandAction,
    CommandScope,
    job_type_for_command,
)
from packages.application.candidate_service import CandidateService
from packages.domain.entity import CanonState, EntityType, NarrativeEntity, VisibilityState
from packages.domain.project import Project
from packages.domain.result import Ok


class FakeProvider:
    """Real-ish provider (provider_name != 'simulated') returning fixed JSON."""

    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response: str = "{}"):
        self.response = response
        self.calls: list[dict] = []

    def chat(
        self, system_prompt, user_message, timeout=None, *,
        temperature=None, max_tokens=None, json_mode=False,
    ):
        self.calls.append({"json_mode": json_mode, "user": user_message})
        return self.response, None


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _project():
    project = Project(name="Async consolidation")
    project.entities.append(NarrativeEntity(
        id="ent_1",
        name="Ariadna",
        entity_type=EntityType.PERSONAJE,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
        brief_description="Exploradora",
    ))
    return project


# --- F1.6 consolidation ----------------------------------------------------

def test_context_service_reuses_injected_job_service():
    shared = AIJobService(provider=FakeProvider("{}"))
    ps = FakeProjectService(_project())
    svc = AIContextActionService(ps, CandidateService(ps), ai_job_service=shared)
    # Same registry, and provider/allow_simulated derived from the shared one.
    assert svc._jobs is shared
    assert svc.provider is shared.provider
    assert svc.allow_simulated == shared.allow_simulated


def test_context_action_registers_job_in_shared_registry():
    shared = AIJobService(provider=FakeProvider('{"hojas": [{"name": "Aliada"}]}'))
    ps = FakeProjectService(_project())
    svc = AIContextActionService(ps, CandidateService(ps), ai_job_service=shared)

    assert shared.list_jobs() == []
    result = svc.run_node_action("ent_1", "create_candidate", prompt_hint="una aliada")
    assert isinstance(result, Ok)
    # The contextual job is now visible in the shared command-bar registry.
    jobs = shared.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].status == AIJobStatus.READY_FOR_REVIEW


def test_without_injection_context_service_owns_a_private_registry():
    ps = FakeProjectService(_project())
    svc = AIContextActionService(ps, CandidateService(ps), provider=FakeProvider("{}"))
    assert isinstance(svc._jobs, AIJobService)


# --- F1.4 determinism: explicit intent is authoritative --------------------

def test_explicit_job_type_is_not_reclassified():
    shared = AIJobService(provider=FakeProvider("{}"))
    # Prompt text screams "create a character" (old classifier -> GENERATE_ENTITIES)
    # but the explicit selection is ANALIZAR/coherence. Explicit must win.
    job_type = job_type_for_command(CommandAction.ANALIZAR, CommandScope.HOJA)
    created = shared.create_job(job_type, "crea un personaje nuevo", explicit=True)
    assert isinstance(created, Ok)
    job = created.value
    assert job.type is AIJobType.ANALYZE_COHERENCE
    assert job.explicit_intent is AIJobType.ANALYZE_COHERENCE


def test_set_provider_swaps_simulated_for_real_and_unblocks_jobs():
    # Default service uses the simulated provider, which the command bar refuses.
    service = AIJobService()
    assert service.provider.provider_name == "simulated"
    blocked = service.run_focused_job(AIJobType.CREATE_RING_TEMPLATE, "crea anillos", context_scope={})
    assert blocked.__class__.__name__ == "Error"  # simulated guard fires

    # After the user configures a real provider, set_provider swaps it in-place.
    real = FakeProvider('{"summary": "ok"}')
    service.set_provider(real)
    assert service.provider is real
    result = service.run_focused_job(AIJobType.CREATE_RING_TEMPLATE, "crea anillos", context_scope={})
    assert isinstance(result, Ok)
    assert result.value.status == AIJobStatus.READY_FOR_REVIEW


def test_focused_job_runs_new_ring_template_type_end_to_end():
    response = '{"summary": "Plantilla lista", "ramas": [{"name": "Materia"}]}'
    shared = AIJobService(provider=FakeProvider(response))
    result = shared.run_focused_job(
        AIJobType.CREATE_RING_TEMPLATE,
        "Crea la plantilla de anillos base del proyecto",
        context_scope={},
    )
    assert isinstance(result, Ok)
    job = result.value
    assert job.type is AIJobType.CREATE_RING_TEMPLATE
    assert job.status == AIJobStatus.READY_FOR_REVIEW
