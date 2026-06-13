"""H06: milestone deletion and simplified chronology modes."""

from __future__ import annotations

from types import SimpleNamespace

from packages.application.causal_milestone_service import CausalMilestoneService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.result import Error


def test_delete_hito_removes_it_and_unlinks_project_chronology():
    project = Project(name="H06")
    parent = CausalMilestone(id="hito-parent", title="Padre", causal_child_hito_ids=["hito-delete"])
    child = CausalMilestone(id="hito-child", title="Hijo", causal_parent_hito_ids=["hito-delete"])
    target = CausalMilestone(id="hito-delete", title="Eliminar")
    project.causal_milestones = [parent, target, child]
    project.project_chronology.link_milestone("hito-delete")
    ps = SimpleNamespace(active_project=project)
    service = CausalMilestoneService(ps)

    result = service.delete_hito("hito-delete")

    assert not isinstance(result, Error)
    assert [h.id for h in project.causal_milestones] == ["hito-parent", "hito-child"]
    assert project.project_chronology.milestone_ids == []
    assert parent.causal_child_hito_ids == []
    assert child.causal_parent_hito_ids == []


def test_delete_missing_hito_returns_error():
    service = CausalMilestoneService(SimpleNamespace(active_project=Project(name="H06")))

    result = service.delete_hito("missing")

    assert isinstance(result, Error)
