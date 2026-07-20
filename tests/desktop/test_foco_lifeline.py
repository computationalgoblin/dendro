"""Cronología local de Foco: span arrastrable, hitos clicables y creación (BETA2-FOCO-10)."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.causal_milestone import (  # noqa: E402 — tras el guard HAS_QT
    CausalMilestone,
    CausalMilestoneStatus,
)
from packages.domain.entity import NarrativeEntity  # noqa: E402 — tras el guard HAS_QT


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _band():
    from hosts.DesktopHostPySide.widgets.foco.foco_lifeline import FocoLifelineBand

    band = FocoLifelineBand()
    band.resize(640, 64)
    return band


def _entity(name="Eldrin", birth=1000, death=1050):
    return NarrativeEntity(name=name, birth_year=birth, death_year=death)


def _milestone(entity_id, title, year):
    return CausalMilestone(
        title=title,
        year=year,
        status=CausalMilestoneStatus.CANON,
        affected_entity_ids=[entity_id],
    )


def _era(name, start, end, order):
    # BETA2-CAL-08: era de contexto (mismo pato que domain.Era / _EraSpan).
    return SimpleNamespace(name=name, start_year=start, end_year=end, order=order)


class TestScaleAndMarks:
    def test_linear_scale_roundtrip(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [_milestone(entity.id, "Guerra", 1010)])

        assert band.x_at(1000) < band.x_at(1025) < band.x_at(1050)
        assert abs(band.year_at(band.x_at(1025)) - 1025) <= 1

    def test_milestone_hit_and_activation(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        seen: list[str] = []
        band.milestoneActivated.connect(seen.append)

        assert band.milestone_at(band.x_at(1010)) == milestone.id
        band.activate_milestone(band.milestone_at(band.x_at(1010)))
        assert seen == [milestone.id]

    def test_undated_entity_shows_hint_without_crash(self, qapp):
        band = _band()
        band.set_entity(NarrativeEntity(name="Sin fechas"))
        assert band.span() == (None, None)
        band.repaint()  # pintado del estado "sin datación" no revienta offscreen


class TestSpanDrag:
    def test_drag_death_emits_global_signature(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        band.set_span_by_drag("death", 1080)
        assert seen == [(entity.id, 1000, 1080)]
        assert band.span() == (1000, 1080)

    def test_drag_birth_clamps_to_death(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        band.set_span_by_drag("birth", 1990)  # más allá de la muerte → clamp
        assert seen == [(entity.id, 1050, 1050)]

    def test_create_button_uses_span_midpoint(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.milestoneCreateRequested.connect(lambda year, era: seen.append((year, era)))

        band._request_create()
        assert seen == [(1025, "")]


class TestMilestoneSpan:
    """FOCO-25: hitos con inicio y fin (lapso por duración) en la banda local."""

    def test_milestone_with_duration_exposes_end_year(self, qapp):
        from packages.domain.temporal_models import EventTemporality

        band = _band()
        entity = _entity()
        milestone = CausalMilestone(
            title="Guerra larga",
            year=1010,
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=[entity.id],
            temporality=EventTemporality(
                year=1010, is_duration=True, duration_value=15, duration_unit="años"
            ),
        )
        band.set_entity(entity, [milestone])
        assert band._marks[0].end_year == 1025
        # El rango de la escala abarca el fin del lapso.
        low, high = band._year_range()
        assert high >= 1025
        band.repaint()  # la barra inicio→fin pinta sin reventar offscreen

    def test_drag_start_shifts_end_optimistically(self, qapp):
        from packages.domain.temporal_models import EventTemporality

        band = _band()
        entity = _entity()
        milestone = CausalMilestone(
            title="Guerra larga",
            year=1010,
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=[entity.id],
            temporality=EventTemporality(
                year=1010, is_duration=True, duration_value=15, duration_unit="años"
            ),
        )
        band.set_entity(entity, [milestone])
        band.set_milestone_year_by_drag(milestone.id, 1020)
        # La duración se conserva: el fin se desplaza con el inicio.
        assert band._marks[0].year == 1020
        assert band._marks[0].end_year == 1035


class TestMilestoneLanes:
    """FOCO-26: hitos que comparten espacio temporal NO se solapan (carriles)."""

    def test_same_year_milestones_get_distinct_lanes(self, qapp):
        band = _band()
        entity = _entity()
        first = _milestone(entity.id, "Guerra", 1010)
        second = _milestone(entity.id, "Pacto", 1010)
        band.set_entity(entity, [first, second])
        lanes = band._lanes()
        assert lanes[first.id] != lanes[second.id]

    def test_distant_milestones_share_lane_zero(self, qapp):
        band = _band()
        entity = _entity()
        first = _milestone(entity.id, "Guerra", 1005)
        second = _milestone(entity.id, "Pacto", 1045)
        band.set_entity(entity, [first, second])
        lanes = band._lanes()
        assert lanes[first.id] == 0
        assert lanes[second.id] == 0

    def test_empty_drag_pans_not_create(self, qapp):
        # BETA2-CAL-08: arrastrar en vacío DESPLAZA (pan); ya no crea un hito por
        # rango. La señal se conserva (compat del wiring) pero la banda no la emite.
        band = _band()
        seen: list[tuple] = []
        band.milestoneRangeCreateRequested.connect(lambda a, b: seen.append((a, b)))
        entity = _entity()
        band.set_entity(entity, [], eras=[_era("Todo", 0, None, 0)], present_year=1100)
        before = band.view_range()
        band._begin_pan(band.x_at(1025))
        band._apply_pan(band.x_at(1025) - 40)  # arrastrar 40 px
        band._panning = False
        assert band.view_range() != before  # desplazó
        assert seen == []  # no creó nada
        assert hasattr(band, "milestoneRangeCreateRequested")


class TestViewportAndEras:
    """BETA2-CAL-08: eras de contexto + ventana de vista (zoom/pan/fit)."""

    def _seeded(self):
        band = _band()
        entity = _entity(birth=1010, death=1040)
        marks = [
            _milestone(entity.id, "a", 1015),
            _milestone(entity.id, "b", 1016),
            _milestone(entity.id, "c", 1035),
        ]
        eras = [
            _era("Antigua", 0, 999, 0),
            _era("Media", 1000, 1099, 1),
            _era("Ahora", 1100, None, 2),
        ]
        band.set_entity(entity, marks, eras=eras, present_year=1150)
        return band, entity, marks

    def test_default_view_frames_the_lifespan(self, qapp):
        band, _e, _m = self._seeded()
        assert band.view_range() == band._year_range()  # sin zoom = encuadre por defecto
        lo, hi = band.view_range()
        assert lo <= 1010 and hi >= 1040  # cubre el lapso

    def test_calendar_range_spans_eras_and_present(self, qapp):
        band, _e, _m = self._seeded()
        cal = band._calendar_range()
        assert cal is not None and cal[0] <= 0 and cal[1] >= 1150

    def test_zoom_in_separates_close_milestones(self, qapp):
        band, _e, _m = self._seeded()
        gap0 = band.x_at(1016) - band.x_at(1015)
        band.zoom_view(1015, True)
        band.zoom_view(1015, True)
        assert (band.x_at(1016) - band.x_at(1015)) > gap0  # se separan

    def test_zoom_out_clamps_to_calendar(self, qapp):
        band, _e, _m = self._seeded()
        for _ in range(50):
            band.zoom_view(1025, False)
        lo, hi = band.view_range()
        cal = band._calendar_range()
        assert round(lo) == round(cal[0]) and round(hi) == round(cal[1])

    def test_pan_clamps_within_calendar(self, qapp):
        band, _e, _m = self._seeded()
        band.pan_view(10_000)  # desplazar muy a la derecha
        _lo, hi = band.view_range()
        assert hi <= band._calendar_range()[1] + 1

    def test_fit_restores_default_after_zoom(self, qapp):
        band, _e, _m = self._seeded()
        default = band.view_range()
        band.zoom_view(1020, True)
        assert band.view_range() != default
        band.fit()
        assert band.view_range() == default

    def test_eras_stored_and_paint_ok(self, qapp):
        band, _e, _m = self._seeded()
        assert band._eras and band._present_year == 1150
        band.repaint()  # eras de fondo + presente, sin fallo en offscreen

    def test_set_entity_without_eras_keeps_working(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [_milestone(entity.id, "x", 1025)])  # firma antigua
        assert band._eras == []
        assert band.year_at(band.x_at(1025)) == pytest.approx(1025, abs=1)
        band.repaint()


class TestQuickCreateEndYear:
    """FOCO-26: el diálogo de crear hito acepta «Año fin» (lapso por duración)."""

    def test_payload_carries_duration_when_end_set(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import MilestoneQuickCreatePanel

        panel = MilestoneQuickCreatePanel(default_year=100, calendar_meta={}, default_end_year=140)
        payload = panel.payload()
        assert payload["year"] == 100
        assert payload["temporality"]["is_duration"] is True
        assert payload["temporality"]["duration_value"] == 40

    def test_payload_without_end_is_point_milestone(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import MilestoneQuickCreatePanel

        panel = MilestoneQuickCreatePanel(default_year=100, calendar_meta={})
        payload = panel.payload()
        assert "temporality" not in payload


class TestMilestoneDrag:
    """FOCO-25: arrastrar el rombo de un hito reubica su año."""

    def test_milestone_drag_emits_year_and_updates_mark(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        seen: list[tuple] = []
        band.milestoneYearEdited.connect(lambda mid, year: seen.append((mid, year)))

        band.set_milestone_year_by_drag(milestone.id, 1030)
        assert seen == [(milestone.id, 1030)]
        # Marca reubicada optimista: el rombo responde en su nueva posición.
        assert band.milestone_at(band.x_at(1030)) == milestone.id

    def test_click_without_drag_still_activates(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        activated: list[str] = []
        band.milestoneActivated.connect(activated.append)

        band.activate_milestone(band.milestone_at(band.x_at(1010)))
        assert activated == [milestone.id]


class TestReadOnlyMode:
    """BETA2-FOCO-27: en la tarjeta de descripción la cronología es SOLO lectura."""

    def _press(self, band, x, *, y_offset=-8):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        pos = QPointF(x, band._axis_y + y_offset)
        return QMouseEvent(
            QEvent.Type.MouseButtonPress,
            pos,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def _release(self, band, x, *, y_offset=-8):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        pos = QPointF(x, band._axis_y + y_offset)
        return QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            pos,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def test_read_only_hides_create_button(self, qapp):
        band = _band()
        band.set_read_only(True)
        assert band._add_button.isHidden()
        band.set_read_only(False)
        assert not band._add_button.isHidden()

    def test_read_only_blocks_span_edge_drag(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        band.set_read_only(True)
        band.mousePressEvent(self._press(band, band.x_at(1000)))  # borde de origen
        assert band._drag_edge == ""  # sin arrastre de lapso en lectura

    def test_read_only_click_still_activates_milestone(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        band.set_read_only(True)
        activated: list[str] = []
        band.milestoneActivated.connect(activated.append)

        x = band.x_at(1010)
        band.mousePressEvent(self._press(band, x))
        band.mouseReleaseEvent(self._release(band, x))
        assert activated == [milestone.id]


class TestFocoViewIntegration:
    def _setup(self):
        project_service = ProjectService()
        project_service.create("Lifeline")
        from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
            CausalMilestoneController,
        )
        from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        ctx = SimpleNamespace(
            advanced_mode=False,
            log=lambda *args, **kwargs: None,
            animation_duration=lambda default=220: 0,
            request_save_silent=lambda: None,
            selected_entity_id=None,
            project_controller=SimpleNamespace(ps=project_service),
        )
        milestone_controller = CausalMilestoneController(project_service)
        view = FocoView(
            project_provider=lambda: project_service.active_project,
            ctx=ctx,
            entity_controller=EntityController(project_service),
            milestone_controller=milestone_controller,
        )
        return project_service, view

    def test_lifeline_loads_entity_and_milestones(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        project.entities.append(entity)
        project.causal_milestones.append(_milestone(entity.id, "Guerra", 1010))
        project.touch()

        view.center_entity(entity.id)
        assert not view.lifeline.isHidden()
        assert view.lifeline.entity_id() == entity.id
        assert len(view.lifeline.milestone_ids()) == 1

    def test_span_edit_reemits_for_workspace_persistence(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project_service.active_project.entities.append(entity)
        project_service.active_project.touch()
        view.center_entity(entity.id)
        seen: list[tuple] = []
        view.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        view.lifeline.set_span_by_drag("death", 1090)
        assert seen == [(entity.id, 1000, 1090)]

    def test_milestone_click_opens_adjacent_panel(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        milestone = _milestone(entity.id, "Guerra", 1010)
        project.entities.append(entity)
        project.causal_milestones.append(milestone)
        project.touch()
        view.center_entity(entity.id)

        view.lifeline.activate_milestone(milestone.id)
        assert not view._adjacent_card.isHidden()
        assert view._adjacent_title.full_text() == "Hito"

    def test_milestone_click_in_reading_opens_read_card(self, qapp):
        # BETA2-FOCO-27: en descripción el clic abre el panel COMPACTO de lectura.
        from hosts.DesktopHostPySide.widgets.foco.milestone_read_card import MilestoneReadCard

        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        milestone = _milestone(entity.id, "Guerra", 1010)
        project.entities.append(entity)
        project.causal_milestones.append(milestone)
        project.touch()
        view.center_entity(entity.id)

        assert not view._editor_open
        view.lifeline.activate_milestone(milestone.id)
        assert isinstance(view._adjacent_scroll.widget(), MilestoneReadCard)
        assert view._bottom_sheet.isHidden()

    def test_milestone_click_in_editor_opens_bottom_sheet(self, qapp):
        # BETA2-FOCO-27: en edición el clic abre el cajón inferior con el panel
        # editable completo (no la tarjeta adyacente de lectura).
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        milestone = _milestone(entity.id, "Guerra", 1010)
        project.entities.append(entity)
        project.causal_milestones.append(milestone)
        project.touch()
        view.center_entity(entity.id)
        view.open_editor()
        assert view._editor_open

        view.lifeline.activate_milestone(milestone.id)
        assert not view._bottom_sheet.isHidden()
        assert isinstance(view._bottom_sheet.content(), MilestoneDetailPanel)
        assert view._adjacent_card.isHidden()  # NO usa el flyout de lectura
        # Cerrar el editor cierra también el cajón.
        view.close_editor()
        assert view._bottom_sheet.isHidden()


class TestWorkspaceWiring:
    def test_lifeline_signals_reuse_global_slots(self):
        source = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
        assert "self.foco.lifespanEdited.connect(self._on_lifespan_edited)" in source
        # FOCO-25: la creación desde el Foco pasa por el slot que VINCULA el
        # hito a la entidad en foco (que reutiliza el flujo global por dentro).
        assert (
            "self.foco.milestoneCreateRequested.connect(self._on_foco_create_milestone)" in source
        )
        assert "affected_entity_ids" in source


class TestMilestoneEndDrag:
    """UI2-14: rombo de FIN — pintado, arrastrable y creable desde la banda."""

    def _spanned_milestone(self, entity_id, year=1010, duration=15):
        from packages.domain.temporal_models import EventTemporality

        return CausalMilestone(
            title="Guerra larga",
            year=year,
            status=CausalMilestoneStatus.CANON,
            affected_entity_ids=[entity_id],
            temporality=EventTemporality(
                year=year, is_duration=True, duration_value=duration, duration_unit="años"
            ),
        )

    def test_end_drag_emits_and_updates_mark(self, qapp):
        band = _band()
        entity = _entity()
        milestone = self._spanned_milestone(entity.id)
        band.set_entity(entity, [milestone])
        seen: list[tuple] = []
        band.milestoneEndYearEdited.connect(lambda mid, year: seen.append((mid, year)))

        band.set_milestone_end_by_drag(milestone.id, 1030)
        assert seen == [(milestone.id, 1030)]
        assert band._marks[0].end_year == 1030

    def test_end_below_start_collapses_to_point(self, qapp):
        band = _band()
        entity = _entity()
        milestone = self._spanned_milestone(entity.id)
        band.set_entity(entity, [milestone])
        seen: list[tuple] = []
        band.milestoneEndYearEdited.connect(lambda mid, year: seen.append((mid, year)))

        band.set_milestone_end_by_drag(milestone.id, 1005)  # fin ≤ inicio
        assert band._marks[0].end_year is None  # hito puntual de nuevo
        assert seen == [(milestone.id, 1010)]  # emite el año de inicio

    def test_end_handle_hit_prefers_start_on_tie(self, qapp):
        band = _band()
        entity = _entity()
        milestone = self._spanned_milestone(entity.id)
        band.set_entity(entity, [milestone])
        assert band.milestone_end_at(band.x_at(1025)) == milestone.id
        milestone_id, edge = band._milestone_hit(band.x_at(1025))
        assert (milestone_id, edge) == (milestone.id, "end")
        # En el inicio, gana el inicio.
        milestone_id, edge = band._milestone_hit(band.x_at(1010))
        assert (milestone_id, edge) == (milestone.id, "start")

    def test_shift_press_on_start_arms_end_drag(self, qapp):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Puntual", 1010)
        band.set_entity(entity, [milestone])
        x = band.x_at(1010)
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(x, band._axis_y - 8),
            QPointF(x, band._axis_y - 8),
            QPointF(x, band._axis_y - 8),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier,
        )
        band.mousePressEvent(event)
        assert band._drag_milestone_id == milestone.id
        assert band._drag_milestone_edge == "end"

    def test_ghost_end_handle_appears_on_hover_for_point_milestones(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Puntual", 1010)
        band.set_entity(entity, [milestone])
        x = band.x_at(1010)
        band._hover_x = x  # el cursor está sobre el rombo
        assert band._ghost_end_at(x + 14.0) == milestone.id
        band._hover_x = None  # sin hover no hay fantasma
        assert band._ghost_end_at(x + 14.0) == ""
        band.repaint()  # pinta el fantasma sin reventar offscreen

    def test_end_drag_persists_duration_through_controller(self, qapp):
        integration = TestFocoViewIntegration()
        project_service, view = integration._setup()
        entity = _entity()
        project = project_service.active_project
        milestone = _milestone(entity.id, "Guerra", 1010)
        project.entities.append(entity)
        project.causal_milestones.append(milestone)
        project.touch()
        view.center_entity(entity.id)

        view.lifeline.set_milestone_end_by_drag(milestone.id, 1030)

        stored = next(m for m in project.causal_milestones if m.id == milestone.id)
        assert stored.temporality is not None
        assert stored.temporality.is_duration is True
        assert stored.temporality.duration_value == 20
        assert stored.as_temporal_span().end_year == 1030


class TestLapsoShadowAndUndated:
    """BETA2-FOCO-29: lapso como sombra definible sin datar + modo lapso_only."""

    def _evt(self, kind, band, x):
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        p = QPointF(x, band._axis_y)
        released = kind == QEvent.Type.MouseButtonRelease
        buttons = Qt.MouseButton.NoButton if released else Qt.MouseButton.LeftButton
        return QMouseEvent(
            kind, p, p, p, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
        )

    def _press(self, band, x):
        from PySide6.QtCore import QEvent

        return self._evt(QEvent.Type.MouseButtonPress, band, x)

    def _move(self, band, x):
        from PySide6.QtCore import QEvent

        return self._evt(QEvent.Type.MouseMove, band, x)

    def _release(self, band, x):
        from PySide6.QtCore import QEvent

        return self._evt(QEvent.Type.MouseButtonRelease, band, x)

    def test_undated_birth_is_placeholder_death_hidden(self, qapp):
        band = _band()
        band.set_entity(NarrativeEntity(name="SinDatar"))
        hx, ph = band._handle_x("birth")
        assert hx is not None and ph is True
        assert band._handle_x("death") == (None, False)  # el fin se ofrece tras fijar inicio

    def test_undated_drag_placeholder_fixes_birth(self, qapp):
        band = _band()
        band.set_entity(NarrativeEntity(name="SinDatar"))
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, bi, de: seen.append((bi, de)))
        hx, _ph = band._handle_x("birth")
        band.mousePressEvent(self._press(band, hx))
        band.mouseMoveEvent(self._move(band, band.x_at(5)))
        band.mouseReleaseEvent(self._release(band, band.x_at(5)))
        assert band.span()[0] == 5
        assert seen and seen[-1][0] == 5
        # ya con inicio, el fin se ofrece (placeholder en el extremo abierto)
        assert band._handle_x("death")[0] is not None

    def test_undated_read_only_has_no_placeholder(self, qapp):
        band = _band()
        band.set_entity(NarrativeEntity(name="SinDatar"))
        band.set_read_only(True)
        band.repaint()  # solo aviso "Sin datar"; no revienta offscreen
        # en lectura no se arma arrastre del lapso
        band.mousePressEvent(self._press(band, band._handle_x("birth")[0]))
        assert band._drag_edge == ""

    def test_lapso_only_hides_create_button(self, qapp):
        band = _band()
        band.set_entity(_entity(), [])
        band.set_read_only(False)
        band.set_lapso_editable_only(True)
        assert band._add_button.isHidden()

    def test_lapso_only_allows_span_drag(self, qapp):
        band = _band()
        band.set_entity(_entity(), [])
        band.set_read_only(False)
        band.set_lapso_editable_only(True)
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, bi, de: seen.append((bi, de)))
        hx, _ph = band._handle_x("death")  # asa real en 1050
        band.mousePressEvent(self._press(band, hx))
        band.mouseMoveEvent(self._move(band, band.x_at(1030)))
        band.mouseReleaseEvent(self._release(band, band.x_at(1030)))
        assert band.span()[1] == 1030
        assert seen and seen[-1][1] == 1030

    def test_lapso_only_blocks_milestone_drag_but_click_activates(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        band.set_read_only(False)
        band.set_lapso_editable_only(True)
        moved: list[tuple] = []
        activated: list[str] = []
        band.milestoneYearEdited.connect(lambda mid, y: moved.append((mid, y)))
        band.milestoneActivated.connect(activated.append)
        x = band.x_at(1010)
        # arrastrar el rombo NO lo mueve
        band.mousePressEvent(self._press(band, x))
        band.mouseMoveEvent(self._move(band, band.x_at(1030)))
        band.mouseReleaseEvent(self._release(band, band.x_at(1030)))
        assert moved == []
        # clic (sin mover) SÍ abre el hito
        band.mousePressEvent(self._press(band, x))
        band.mouseReleaseEvent(self._release(band, x))
        assert activated == [milestone.id]
