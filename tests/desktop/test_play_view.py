"""BETA2-PLAY — PlayView: escena inmersiva del recorrido cronológico (offscreen).

La vista se prueba como widget REAL (offscreen). El cableado del workspace
(cuarto estado "play", entrada desde la config del walk, salida a Cronología)
se verifica con pins de fuente, patrón de la casa (``test_foco_default_view``):
construir el CreationWorkspace completo headless cuelga PySide6.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _project_and_walk():
    """Proyecto real con dos hitos vinculados y un recorrido activo en h2."""
    from packages.application.causal_milestone_service import CausalMilestoneService
    from packages.application.chronology_walk_service import ChronologyWalkService
    from packages.application.entity_service import EntityService
    from packages.application.project_service import ProjectService

    ps = ProjectService()
    ps.create("PLAY escena")
    entity = (
        EntityService(ps, ps.store)
        .create_entity({"name": "Devian", "entity_type": "personaje", "birth_year": -100})
        .value
    )
    milestones = CausalMilestoneService(project_service=ps)
    h1 = milestones.create_hito_manual(
        {"title": "Origen", "year": 100, "affected_entity_ids": [entity.id]}
    ).value
    h2 = milestones.create_hito_manual(
        {
            "title": "La Purga",
            "year": 200,
            "description": "La ciudad cayó tras el pacto roto.",
            "affected_entity_ids": [entity.id],
            "causal_parent_hito_ids": [h1.id],
        }
    ).value
    ps.active_project.project_chronology.ensure_default_era()
    walk = ChronologyWalkService(project_service=ps, ai_job_service=None)
    session = walk.start_walk(h2.id).value
    return ps, walk, session, h1, h2


def _view(ps):
    from hosts.DesktopHostPySide.widgets.play.play_view import PlayView

    return PlayView(project_provider=lambda: ps.active_project)


class TestPlayScene:
    def test_scene_renders_title_year_era_and_progress(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        scene = walk.step_scene(session.id).value

        view = _view(ps)
        view.show_scene(scene)

        assert view.title_label.text() == "La Purga"
        assert view.year_label.text() == "Año 200"
        assert view.era_label.text() == "PRESENTE"  # era default del calendario
        assert view.progress_label.text() == "HITO 2 DE 2"
        assert "pacto roto" in view.desc_label.text()

    def test_scene_shows_portrait_chip_per_affected_entity(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        scene = walk.step_scene(session.id).value

        view = _view(ps)
        view.show_scene(scene)

        layout = view.portraits_row.layout()
        # 2 stretch de los extremos + 1 chip (Devian, sin imagen → inicial).
        assert layout.count() == 3

    def test_scene_without_year_shows_por_datar(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        scene = walk.step_scene(session.id).value
        scene = dict(scene)
        scene["hito"] = {**scene["hito"], "year": None}

        view = _view(ps)
        view.show_scene(scene)

        assert view.year_label.text() == "Por datar"

    def test_exit_button_emits_signal(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)

        fired: list[bool] = []
        view.exitRequested.connect(lambda: fired.append(True))
        view.exit_btn.click()

        assert fired == [True]

    def test_continue_disabled_until_analysis(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)

        assert view.continue_btn.isEnabled() is False


def _analysis(milestone_id: str, *, stopped: bool, problems=None, summary="Lectura del paso"):
    return {
        "summary": summary,
        "model_payload": {"summary": summary},
        "walk": {
            "session_id": "s",
            "milestone_id": milestone_id,
            "stopped": stopped,
            "stop_reason": "Contradicción dura" if stopped else "",
            "open_problems": list(problems or []),
            "status": "paused" if stopped else "active",
            "position": 2,
            "total": 2,
        },
    }


class TestPlayCycle:
    """PLAY-04: analizando → análisis → (congelado | Continuar)."""

    def test_busy_state_disables_actions(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)

        view.set_busy(True)

        assert view.is_busy
        assert not view.continue_btn.isEnabled()
        assert not view.stop_btn.isEnabled()
        assert "leyendo" in view.status_label.text()
        # PLAY-11: el progreso es inequívoco — indicador girando + botón «Analizando…».
        assert view.busy_indicator.is_running()
        assert view.continue_btn.text() == "Analizando…"

    def test_busy_cleared_restores_indicator_and_button(self, qapp):
        """PLAY-11: al terminar el análisis no queda ningún giro huérfano."""
        ps, walk, session, _h1, h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)
        view.set_busy(True)

        view.show_analysis(_analysis(h2.id, stopped=False))

        assert not view.busy_indicator.is_running()
        assert view.continue_btn.text() == "Continuar ▶"
        view.set_busy(True)
        view.show_error("fallo")
        assert not view.busy_indicator.is_running()
        assert view.continue_btn.text() == "Continuar ▶"

    def test_hard_issue_freezes_scene_and_blocks_continue(self, qapp):
        ps, walk, session, _h1, h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)
        problem = {
            "milestone_id": h2.id,
            "title": "Muerta antes del hito",
            "description": "Mirra muere en 398 pero participa en 412.",
            "kind": "contradiction",
            "severity": "alta",
            "resolved": False,
        }

        view.show_analysis(_analysis(h2.id, stopped=True, problems=[problem]))

        assert view.is_frozen
        assert not view.continue_btn.isEnabled()
        assert not view.issues_frame.isHidden()
        assert "congelada" in view.status_label.text().lower()

    def test_clean_analysis_enables_continue_and_shows_reading(self, qapp):
        ps, walk, session, _h1, h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)

        view.show_analysis(_analysis(h2.id, stopped=False, summary="Todo encaja."))

        assert not view.is_frozen
        assert view.continue_btn.isEnabled()
        assert view.reading_label.text() == "Todo encaja."
        assert view.issues_frame.isHidden()

    def test_error_keeps_scene_readable_and_navigation_alive(self, qapp):
        ps, walk, session, _h1, _h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)
        view.set_busy(True)

        view.show_error("No hay proveedor de IA configurado")

        assert not view.is_busy
        assert "proveedor" in view.status_label.text()
        assert view.title_label.text() == "La Purga"  # la escena sigue ahí
        assert view.exit_btn.isEnabled()
        assert view.stop_btn.isEnabled()
        assert not view.continue_btn.isEnabled()  # sin análisis no hay avance limpio

    def test_waiting_notice_keeps_waiting_and_offers_retry(self, qapp):
        """PLAY-12: el aviso de lentitud NO cancela — busy sigue y hay Reintentar."""
        ps, walk, session, _h1, h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)
        view.set_busy(True)

        view.show_waiting_notice("La IA está tardando más de lo normal…")

        assert view.is_busy  # se sigue esperando
        assert not view.retry_btn.isHidden()
        assert "tardando" in view.status_label.text()
        fired: list[bool] = []
        view.retryRequested.connect(lambda: fired.append(True))
        view.retry_btn.click()
        assert fired == [True]
        # El resultado tardío llega y limpia el aviso sin contradicciones.
        view.show_analysis(_analysis(h2.id, stopped=False))
        assert view.retry_btn.isHidden()
        assert view.continue_btn.isEnabled()

    def test_error_offers_retry(self, qapp):
        """PLAY-12: un fallo del análisis siempre ofrece reintento."""
        ps, walk, session, _h1, _h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)

        view.show_error("No hay proveedor de IA configurado")

        assert not view.retry_btn.isHidden()

    def test_new_scene_resets_cycle_state(self, qapp):
        ps, walk, session, h1, h2 = _project_and_walk()
        view = _view(ps)
        view.show_scene(walk.step_scene(session.id).value)
        view.show_analysis(_analysis(h2.id, stopped=True))
        assert view.is_frozen

        view.show_scene(walk.step_scene(session.id, h1.id).value)

        assert not view.is_frozen
        assert view.reading_label.isHidden()
        assert view.issues_frame.isHidden()


class TestCausalDetours:
    """PLAY-05: causas/consecuencias navegables sin tocar la sesión."""

    def _wired_view(self):
        ps, walk, session, h1, h2 = _project_and_walk()
        view = _view(ps)
        view.set_scene_getter(lambda mid=None: walk.step_scene(session.id, mid).value)
        view.show_scene(walk.step_scene(session.id).value)
        return ps, walk, session, h1, h2, view

    def test_scene_shows_causal_chips(self, qapp):
        _ps, _walk, _session, _h1, _h2, view = self._wired_view()

        assert len(view.cause_chips) == 1
        assert "Origen" in view.cause_chips[0].text()
        assert not view.links_row.isHidden()

    def test_detour_visits_cause_without_touching_session(self, qapp):
        _ps, _walk, session, _h1, h2, view = self._wired_view()

        view.cause_chips[0].click()

        assert view.title_label.text() == "Origen"
        assert view.progress_label.text().startswith("VISITA")
        assert view.is_visiting
        assert not view.back_btn.isHidden()
        assert session.current_milestone_id == h2.id  # la sesión no se mueve
        assert session.visited_milestone_ids == []

    def test_return_restores_current_scene_and_analysis(self, qapp):
        _ps, _walk, _session, _h1, h2, view = self._wired_view()
        view.show_analysis(_analysis(h2.id, stopped=False, summary="Limpio."))
        assert view.continue_btn.isEnabled()

        view.cause_chips[0].click()
        assert not view.continue_btn.isEnabled()  # la visita no hereda el análisis

        view.back_btn.click()

        assert view.title_label.text() == "La Purga"
        assert not view.is_visiting
        assert view.back_btn.isHidden()
        assert view.continue_btn.isEnabled()  # análisis cacheado repuesto
        assert view.reading_label.text() == "Limpio."

    def test_detour_blocked_while_busy(self, qapp):
        _ps, _walk, _session, _h1, _h2, view = self._wired_view()
        view.set_busy(True)

        view.cause_chips[0].click()

        assert view.title_label.text() == "La Purga"  # sin desvío en pleno análisis
        assert not view.is_visiting


class TestInlineEditing:
    """PLAY-06: toda la escena es editable; el canon viaja por editCommitted."""

    def _editing_view(self):
        ps, walk, session, h1, h2 = _project_and_walk()
        view = _view(ps)
        view.set_scene_getter(lambda mid=None: walk.step_scene(session.id, mid).value)
        view.show_scene(walk.step_scene(session.id).value)
        patches: list[tuple[str, dict]] = []
        view.editCommitted.connect(lambda mid, patch: patches.append((mid, dict(patch))))
        return ps, walk, session, h1, h2, view, patches

    def test_title_edit_emits_patch(self, qapp):
        _ps, _walk, _session, _h1, h2, view, patches = self._editing_view()

        view._start_edit("title")
        assert not view.title_edit.isHidden()
        view.title_edit.setText("La Gran Purga")
        view._commit_edit("title")

        assert patches == [(h2.id, {"title": "La Gran Purga"})]
        assert view.title_label.text() == "La Gran Purga"
        assert view.title_edit.isHidden()

    def test_year_edit_parses_int_and_empty(self, qapp):
        _ps, _walk, _session, _h1, h2, view, patches = self._editing_view()

        view._start_edit("year")
        view.year_edit.setText("412")
        view._commit_edit("year")
        view._start_edit("year")
        view.year_edit.setText("")
        view._commit_edit("year")

        assert patches == [(h2.id, {"year": 412}), (h2.id, {"year": None})]
        assert view.year_label.text() == "Por datar"

    def test_invalid_year_is_discarded(self, qapp):
        _ps, _walk, _session, _h1, _h2, view, patches = self._editing_view()

        view._start_edit("year")
        view.year_edit.setText("cuatrocientos")
        view._commit_edit("year")

        assert patches == []

    def test_description_edit_emits_patch(self, qapp):
        _ps, _walk, _session, _h1, h2, view, patches = self._editing_view()

        view._start_edit("description")
        view.desc_edit.setPlainText("Nueva crónica del suceso.")
        view._commit_edit("description")

        assert patches == [(h2.id, {"description": "Nueva crónica del suceso."})]

    def test_link_and_unlink_entity_patch_affected_ids(self, qapp):
        ps, _walk, _session, _h1, h2, view, patches = self._editing_view()
        from packages.application.entity_service import EntityService

        other = (
            EntityService(ps, ps.store)
            .create_entity({"name": "Mirra", "entity_type": "personaje", "birth_year": -50})
            .value
        )

        view._link_entity(other.id)
        view._unlink_entity(other.id)

        assert patches[0][1]["affected_entity_ids"][-1] == other.id
        assert other.id not in patches[1][1]["affected_entity_ids"]

    def test_link_popover_opens_and_survives(self, qapp):
        """PLAY-14: el popover se guarda en referencia de instancia y queda visible."""
        _ps, _walk, _session, _h1, _h2, view, _patches = self._editing_view()

        view.link_entity_btn.click()
        QApplication.processEvents()

        assert view._link_popover is not None
        assert view._link_popover.isVisible()
        view._link_popover.close()

    def test_link_popover_blocked_while_busy_shows_hint(self, qapp):
        """PLAY-14: el gate de busy avisa en vez de callar."""
        _ps, _walk, _session, _h1, _h2, view, _patches = self._editing_view()
        view.set_busy(True)

        view.link_entity_btn.click()

        assert view._link_popover is None
        assert "análisis" in view.status_label.text()

    def test_editing_blocked_while_visiting(self, qapp):
        _ps, _walk, _session, _h1, _h2, view, patches = self._editing_view()
        view.cause_chips[0].click()  # desvío → visita

        view._start_edit("title")

        assert view.title_edit.isHidden()  # en visita no se edita
        assert patches == []


class TestIssueCard:
    """PLAY-07: Corregir (candidatos) / Aplazar sobre la escena congelada."""

    def _frozen_view(self):
        ps, walk, session, h1, h2 = _project_and_walk()
        view = _view(ps)
        view.set_scene_getter(lambda mid=None: walk.step_scene(session.id, mid).value)
        view.show_scene(walk.step_scene(session.id).value)
        problem = {
            "milestone_id": h2.id,
            "title": "Contradicción",
            "description": "d",
            "kind": "contradiction",
            "severity": "alta",
            "resolved": False,
        }
        view.show_analysis(_analysis(h2.id, stopped=True, problems=[problem]))
        return view, h2

    def test_defer_button_visible_when_frozen_and_emits(self, qapp):
        view, _h2 = self._frozen_view()
        assert not view.defer_btn.isHidden()
        fired: list[bool] = []
        view.deferRequested.connect(lambda: fired.append(True))

        view.defer_btn.click()

        assert fired == [True]

    def test_mark_deferred_unfreezes_with_visible_trace(self, qapp):
        view, _h2 = self._frozen_view()

        view.mark_deferred()

        assert not view.is_frozen
        assert view.continue_btn.isEnabled()
        assert view.defer_btn.isHidden()
        assert "aplazadas" in view.status_label.text()
        assert not view.issues_frame.isHidden()  # la marca del aplazado persiste

    def test_set_changes_and_apply_selected(self, qapp):
        view, _h2 = self._frozen_view()
        view.set_changes(
            [
                {"candidate_id": "c1", "header": "Editar canon: muerte de Mirra"},
                {"candidate_id": "c2", "header": "Nueva entidad: Orden Gris"},
            ]
        )
        assert not view.changes_frame.isHidden()
        assert not view.apply_btn.isHidden()
        captured: list[list] = []
        view.applyRequested.connect(lambda items: captured.append(list(items)))
        view._change_checks[1][0].setChecked(False)  # rechaza la segunda

        view.apply_btn.click()

        assert captured == [[{"candidate_id": "c1"}]]

    def test_mark_applied_resolves_step(self, qapp):
        view, _h2 = self._frozen_view()
        view.set_changes([{"candidate_id": "c1", "header": "Cambio"}])

        view.mark_applied(1)

        assert not view.is_frozen
        assert view.continue_btn.isEnabled()
        assert view.changes_frame.isHidden()
        assert view.issues_frame.isHidden()
        assert "aplicado" in view.status_label.text()


class TestProposalReview:
    """PLAY-17: «Revisar» → preview del panel real → aceptar/rechazar."""

    def _reviewable_view(self, qapp, payload_getter):
        from PySide6.QtWidgets import QLabel

        ps, walk, session, _h1, h2 = _project_and_walk()
        view = _view(ps)
        view.set_scene_getter(lambda mid=None: walk.step_scene(session.id, mid).value)
        view.show_scene(walk.step_scene(session.id).value)

        # Factory falso: devuelve un widget trivial + el getter del diff.
        def factory(descriptor):
            widget = QLabel(descriptor.get("header", ""))
            return widget, payload_getter

        view.set_preview_factory(factory)
        view.set_changes(
            [
                {
                    "candidate_id": "c1",
                    "header": "Editar Devian",
                    "reviewable": True,
                    "edit_kind": "entity_edits",
                    "target_id": "e1",
                    "edit_fields": {"name": "Devian"},
                },
                {"candidate_id": "c2", "header": "Nueva entidad: Orden Gris"},
            ]
        )
        return view

    def _review_button(self, view):
        from PySide6.QtWidgets import QPushButton

        return next(
            b
            for b in view.changes_frame.findChildren(QPushButton)
            if b.text() == "Revisar"
        )

    def test_reviewable_change_has_review_button_only(self, qapp):
        view = self._reviewable_view(qapp, lambda: {})
        from PySide6.QtWidgets import QPushButton

        buttons = [
            b for b in view.changes_frame.findChildren(QPushButton) if b.text() == "Revisar"
        ]
        assert len(buttons) == 1  # solo la propuesta editable ofrece Revisar

    def test_open_review_swaps_scene_for_preview(self, qapp):
        view = self._reviewable_view(qapp, lambda: {})

        self._review_button(view).click()

        assert not view.review_card.isHidden()
        assert view.scene_card.isHidden()

    def test_accept_review_carries_edited_data(self, qapp):
        view = self._reviewable_view(qapp, lambda: {"name": "Devian el Roto", "birth_year": -120})
        self._review_button(view).click()

        view.review_accept_btn.click()

        assert view.review_card.isHidden()  # vuelve a la escena
        assert not view.scene_card.isHidden()
        captured: list[list] = []
        view.applyRequested.connect(lambda items: captured.append(list(items)))
        view.apply_btn.click()
        # El diff editado viaja como edited_data con el edit_fields COMPLETO.
        c1 = next(i for i in captured[0] if i["candidate_id"] == "c1")
        assert c1["edited_data"] == {
            "edit_fields": {"name": "Devian el Roto", "birth_year": -120}
        }

    def test_reject_review_unchecks_and_restores(self, qapp):
        view = self._reviewable_view(qapp, lambda: {"name": "X"})
        self._review_button(view).click()

        view.review_reject_btn.click()

        assert view.review_card.isHidden()
        assert not view.scene_card.isHidden()
        c1_check = next(chk for chk, cid in view._change_checks if cid == "c1")
        assert not c1_check.isChecked()  # rechazada queda fuera del apply
        captured: list[list] = []
        view.applyRequested.connect(lambda items: captured.append(list(items)))
        view.apply_btn.click()
        assert all(i["candidate_id"] != "c1" for i in captured[0])

    def test_review_blocked_while_busy(self, qapp):
        view = self._reviewable_view(qapp, lambda: {})
        view.set_busy(True)

        self._review_button(view).click()

        assert view.review_card.isHidden()  # sin revisar en pleno análisis


class TestChronoWalkCamera:
    """Cámara del walk sobre el canvas (migrado de test_chronology_walk_runner
    al retirar el runner en PLAY-10; la cámara sigue viva en _run_walk_step)."""

    def test_center_on_milestone_centers_and_highlights(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

        ps, _walk, _session, _h1, h2 = _project_and_walk()
        view = ChronoCanvasView()
        view.set_project(ps.active_project)

        assert view.center_on_milestone(h2.id) is True
        assert view._walk_highlight_id == h2.id

        view.clear_walk_highlight()
        assert view._walk_highlight_id is None

    def test_center_on_unknown_milestone_returns_false(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

        ps, _walk, _session, _h1, _h2 = _project_and_walk()
        view = ChronoCanvasView()
        view.set_project(ps.active_project)

        assert view.center_on_milestone("inexistente") is False


class TestWorkspaceWiring:
    """Pins de fuente del cableado en CreationWorkspace (patrón de la casa)."""

    def test_play_is_fourth_view_state(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert 'if view not in ("foco", "concentric", "chrono", "play"):' in source
        assert "self.play = PlayView(" in source
        assert "play_widget.setVisible(play_on)" in source
        assert 'bar.setVisible(view not in ("chrono", "play"))' in source

    def test_walk_config_opens_play_and_exit_returns_to_chrono(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self._open_play_view()" in source  # entrada desde la config del walk
        assert "def _exit_play" in source
        assert "def _refresh_play_scene" in source
        assert "self.play.exitRequested.connect(self._exit_play)" in source

    def test_play_cycle_is_wired_to_walk_handlers(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # PLAY-04: continuar/detener reusan los handlers del walk; el análisis
        # en hilo alimenta la escena (busy → show_analysis / show_error).
        assert "self.play.continueRequested.connect(self._advance_walk)" in source
        assert "self.play.stopRequested.connect(self._stop_walk)" in source
        assert "self.play.set_busy(True)" in source
        assert "self.play.show_analysis(result)" in source
        assert "self.play.show_error(str(error))" in source
        # La reanudación desde la cronología entra en Play (el runner ya no es la cara).
        assert source.count("self._open_play_view()") >= 2

    def test_watchdog_is_non_terminal_and_retry_is_wired(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # PLAY-12: token de intento + reintento + watchdog que avisa sin cancelar.
        assert "self.play.retryRequested.connect(self._retry_walk_step)" in source
        assert "def _retry_walk_step" in source
        assert "self._walk_step_token += 1" in source
        assert "if token is not None and token != self._walk_step_token:" in source
        timeout_body = source.split("def _on_walk_watchdog_timeout")[1].split("\n    def ")[0]
        assert "show_waiting_notice" in timeout_body
        assert "show_error" not in timeout_body  # nunca más «se canceló» en falso
        assert "_walk_analyzing = False" not in timeout_body  # no cancela nada

    def test_apply_does_not_eject_from_play(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # PLAY-13 (doble cinturón): _refresh_after_walk hace refresco ligero en
        # Play, y refresh() no fuerza Foco mientras el recorrido está activo.
        assert "# PLAY-13: dentro de Play, JAMÁS el refresco completo" in source
        refresh_after = source.split("def _refresh_after_walk")[1].split("def ")[0]
        assert "self._mark_graph_stale()" in refresh_after
        assert "self._refresh_chrono_only()" in refresh_after
        assert 'and self._active_view != "play"' in source  # guarda en refresh()

    def test_editing_defer_and_apply_are_wired(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # PLAY-06/07: edición inline, aplazar y aplicar candidatos.
        assert "self.play.editCommitted.connect(self._on_play_edit)" in source
        assert "def _on_play_edit" in source
        assert "self.play.deferRequested.connect(self._defer_walk)" in source
        assert "def _defer_walk" in source
        assert "self.play.applyRequested.connect(self._on_walk_apply)" in source
        assert "self.play.set_changes(self._build_step_changes(" in source
        assert "self.play.mark_applied(len(applied))" in source
        assert "self.play.mark_deferred()" in source

    def test_proposal_review_is_wired(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # PLAY-17: factory de preview + resolución de objetivo + rama edit_fields.
        assert "self.play.set_preview_factory(self._build_proposal_preview)" in source
        assert "def _build_proposal_preview" in source
        assert "def _resolve_edit_target" in source
        assert 'isinstance(pd.get("edit_fields"), dict)' in source
        assert 'preview_patch=patch' in source
