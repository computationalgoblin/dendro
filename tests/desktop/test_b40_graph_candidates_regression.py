"""B40 graph cleanliness regressions.

The creation graph must not show AI candidates as if they were canon entities.
Candidates are review items, not initial graph content.
"""

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication

from packages.domain.candidate_issue import Candidate, CandidateState, CandidateType
from packages.domain.project import Project


def _ctx_for(project):
    return cast(Any, SimpleNamespace(
        advanced_mode=False,
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
    ))


def test_graph_does_not_render_pending_ai_candidates_without_real_entities():
    app = QApplication.instance() or QApplication([])
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

    project = Project(name="Proyecto vacío")
    project.candidates.append(
        Candidate(
            candidate_type=CandidateType.ENTIDAD,
            state=CandidateState.PENDIENTE,
            title="Sugerencia IA fantasma",
            source="ia",
            proposed_data={"name": "Nodo que no debe aparecer", "entity_type": "concepto"},
        )
    )

    graph = GraphCanvasWidget(_ctx_for(project))

    graph.refresh()

    assert not graph.empty.isHidden()
    assert graph.canvas.isHidden()
    assert graph.canvas._all_nodes == []
    assert graph.canvas._all_edges == []


def test_graph_renders_real_entities_even_when_candidates_exist():
    app = QApplication.instance() or QApplication([])
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget
    from packages.domain.entity import NarrativeEntity, EntityType

    project = Project(name="Proyecto con canon")
    project.entities.append(NarrativeEntity(name="Hoja real", entity_type=EntityType.NOTA))
    project.candidates.append(
        Candidate(
            candidate_type=CandidateType.ENTIDAD,
            state=CandidateState.PENDIENTE,
            title="Sugerencia IA no canon",
            source="ia",
            proposed_data={"name": "No renderizar", "entity_type": "concepto"},
        )
    )

    graph = GraphCanvasWidget(_ctx_for(project))

    graph.refresh()

    assert graph.empty.isHidden()
    assert not graph.canvas.isHidden()
    assert [node.name for node in graph.canvas._all_nodes] == ["Hoja real"]
