"""BETA2-WIKI-08: Sugerencias v2 — petición del usuario + navegación de la wiki."""

from dataclasses import dataclass, field
from typing import Any

import pytest

from packages.application.watering_service import WateringService
from packages.application.wiki_navigator import NavigationBundle
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Error, Ok


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _CapturingJobService:
    """AIJobService mínimo: captura la llamada a run_focused_job."""

    calls: list = field(default_factory=list)

    def provider_unconfigured(self):
        return False

    def run_focused_job(self, job_type, prompt, *, context_scope=None, progress_callback=None):
        self.calls.append({"job_type": job_type, "prompt": prompt, "context_scope": context_scope})
        return Ok("job-ok")


@dataclass
class _StubNavigator:
    bundle: Any = None

    def assemble_context(self, request):
        return Ok(self.bundle)


def _service(navigator=None, ai_job_service=None):
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana", brief_description="Reina."))
    ps = _FakeProjectService(active_project=p)
    return WateringService(ps, ai_job_service=ai_job_service, navigator=navigator), p


@pytest.mark.application
def test_peticion_leads_the_prompt():
    svc, _ = _service()
    req = svc.build_suggestion_request("e1", "iluminada", peticion="quiero un rival político")
    assert isinstance(req, Ok)
    assert req.value["prompt"].startswith("PETICIÓN DEL USUARIO (prioritaria): quiero un rival")
    assert req.value["peticion"] == "quiero un rival político"


@pytest.mark.application
def test_suggest_without_peticion_still_works():
    svc, _ = _service()
    req = svc.build_suggestion_request("e1", "iluminada")
    assert isinstance(req, Ok)
    assert "PETICIÓN DEL USUARIO" not in req.value["prompt"]


@pytest.mark.application
def test_suggest_attaches_wiki_context_from_navigator():
    bundle = NavigationBundle(pages=[{"kind": "entity", "id": "e1", "resumen": "Ana"}])
    job = _CapturingJobService()
    svc, _ = _service(navigator=_StubNavigator(bundle=bundle), ai_job_service=job)
    result = svc.suggest("e1", "iluminada", peticion="dame un aliado")
    assert isinstance(result, Ok)
    scope = job.calls[0]["context_scope"]
    assert "contexto_wiki" in scope
    assert scope["contexto_wiki"]["paginas"][0]["id"] == "e1"
    # el foco_hint sigue viajando (germinación en zona)
    assert scope["foco_hint"]["center_entity_id"] == "e1"


@pytest.mark.application
def test_suggest_without_navigator_omits_wiki_context():
    job = _CapturingJobService()
    svc, _ = _service(navigator=None, ai_job_service=job)
    result = svc.suggest("e1", "iluminada")
    assert isinstance(result, Ok)
    assert "contexto_wiki" not in job.calls[0]["context_scope"]


@pytest.mark.application
def test_suggest_empty_bundle_omits_wiki_context():
    job = _CapturingJobService()
    svc, _ = _service(navigator=_StubNavigator(bundle=NavigationBundle()), ai_job_service=job)
    result = svc.suggest("e1", "iluminada")
    assert isinstance(result, Ok)
    assert "contexto_wiki" not in job.calls[0]["context_scope"]


@pytest.mark.application
def test_suggest_navigator_failure_never_breaks():
    @dataclass
    class _FailingNav:
        def assemble_context(self, request):
            return Error("boom")

    job = _CapturingJobService()
    svc, _ = _service(navigator=_FailingNav(), ai_job_service=job)
    result = svc.suggest("e1", "iluminada", peticion="x")
    assert isinstance(result, Ok)  # la sugerencia sigue pese al fallo de navegación
    assert "contexto_wiki" not in job.calls[0]["context_scope"]
