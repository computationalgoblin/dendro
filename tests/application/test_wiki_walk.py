"""BETA2-WIKI-09: el paso del recorrido cronológico (Play/walk) navega la wiki."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from packages.application.chronology_walk_service import ChronologyWalkService
from packages.application.wiki_navigator import NavigationBundle
from packages.domain.project import Project
from packages.domain.result import Ok


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _StubNavigator:
    bundle: Any = None
    seen: list = None

    def assemble_context(self, request):
        (self.seen if self.seen is not None else []).append(request)
        self.last = request
        return Ok(self.bundle)


def _svc(navigator=None):
    ps = _FakeProjectService(active_project=Project(id="p", name="P"))
    return ChronologyWalkService(project_service=ps, ai_job_service=None, navigator=navigator)


@pytest.mark.application
def test_step_attaches_wiki_context():
    bundle = NavigationBundle(canon=[{"kind": "milestone", "id": "h1", "ficha": {}}])
    nav = _StubNavigator(bundle=bundle)
    svc = _svc(navigator=nav)
    ctx: dict = {}
    svc._attach_wiki_context(ctx, SimpleNamespace(id="h1"))
    assert "contexto_wiki" in ctx
    # navega con foco en el hito (kind milestone), sin prompt de usuario.
    assert nav.last.focus_ids == ["h1"]
    assert nav.last.focus_kind == "milestone"
    assert nav.last.user_text == ""


@pytest.mark.application
def test_step_without_navigator_is_noop():
    svc = _svc(navigator=None)
    ctx: dict = {}
    svc._attach_wiki_context(ctx, SimpleNamespace(id="h1"))
    assert "contexto_wiki" not in ctx


@pytest.mark.application
def test_step_empty_bundle_omits_context():
    svc = _svc(navigator=_StubNavigator(bundle=NavigationBundle()))
    ctx: dict = {}
    svc._attach_wiki_context(ctx, SimpleNamespace(id="h1"))
    assert "contexto_wiki" not in ctx
