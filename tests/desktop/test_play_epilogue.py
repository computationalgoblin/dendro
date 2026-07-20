"""BETA2-PLAY-09 — epílogo inmersivo del recorrido (offscreen).

El informe se genera con el SERVICIO real (stop → ChronologyWalkReport) y la
tarjeta debe mostrar títulos humanos (no ids) y los problemas aplazados.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _finished_walk_with_deferred():
    from packages.application.causal_milestone_service import CausalMilestoneService
    from packages.application.chronology_walk_service import ChronologyWalkService
    from packages.application.project_service import ProjectService

    ps = ProjectService()
    ps.create("PLAY epílogo")
    milestones = CausalMilestoneService(project_service=ps)
    h1 = milestones.create_hito_manual({"title": "Origen", "year": 100}).value
    h2 = milestones.create_hito_manual({"title": "La Purga", "year": 200}).value
    walk = ChronologyWalkService(project_service=ps, ai_job_service=None)
    session = walk.start_walk(h1.id).value
    session.visited_milestone_ids.extend([h1.id, h2.id])
    session.open_problems.append(
        {
            "id": "p1",
            "milestone_id": h2.id,
            "kind": "causal_gap",
            "severity": "alta",
            "title": "Hueco causal",
            "description": "",
            "resolved": False,
        }
    )
    walk.defer_problems(session.id, note="al final")
    walk.stop(session.id)
    report = ps.active_project.chronology_walk_reports[0]
    return ps, report, h1, h2


def _texts(widget) -> str:
    return " | ".join(label.text() for label in widget.findChildren(QLabel))


class TestPlayEpilogue:
    def test_epilogue_resolves_titles_and_lists_deferred(self, qapp):
        from hosts.DesktopHostPySide.widgets.play.play_view import PlayView

        ps, report, _h1, _h2 = _finished_walk_with_deferred()
        view = PlayView(project_provider=lambda: ps.active_project)

        view.show_epilogue(report, ps.active_project)

        assert not view.epilogue_card.isHidden()
        assert view.scene_card.isHidden()
        content = _texts(view.epilogue_card)
        assert "Origen (100)" in content and "La Purga (200)" in content  # títulos, no ids
        assert "Hueco causal" in content  # el aplazado reaparece
        assert view.epilogue_card.verdict_label.text() != ""
        assert view.progress_label.text() == "FIN DEL RECORRIDO"

    def test_volver_al_lienzo_emits_exit(self, qapp):
        from hosts.DesktopHostPySide.widgets.play.play_view import PlayView

        ps, report, _h1, _h2 = _finished_walk_with_deferred()
        view = PlayView(project_provider=lambda: ps.active_project)
        view.show_epilogue(report, ps.active_project)
        fired: list[bool] = []
        view.exitRequested.connect(lambda: fired.append(True))

        view.epilogue_card.close_btn.click()

        assert fired == [True]

    def test_new_scene_restores_walk_mode(self, qapp):
        from hosts.DesktopHostPySide.widgets.play.play_view import PlayView
        from packages.application.chronology_walk_service import ChronologyWalkService

        ps, report, h1, _h2 = _finished_walk_with_deferred()
        walk = ChronologyWalkService(project_service=ps, ai_job_service=None)
        session = walk.start_walk(h1.id).value
        view = PlayView(project_provider=lambda: ps.active_project)
        view.show_epilogue(report, ps.active_project)

        view.show_scene(walk.step_scene(session.id).value)

        assert view.epilogue_card.isHidden()
        assert not view.scene_card.isHidden()
        assert not view.continue_btn.isHidden()


class TestEpilogueWiring:
    def test_report_routes_to_epilogue_in_play(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self.play.show_epilogue(report, project)" in source
        assert "self._play_prefetch_cache.clear()" in source  # cierre limpia prefetch
