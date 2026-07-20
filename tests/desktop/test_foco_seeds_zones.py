"""Semillas en Foco: germinación por zonas, tarjetas de texto y chips (BETA2-FOCO-13)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — guard HAS_QT
from packages.domain.candidate_issue import Candidate  # noqa: E402 — guard HAS_QT
from packages.domain.entity import NarrativeEntity  # noqa: E402 — guard HAS_QT

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _view_with_center():
    project_service = ProjectService()
    project_service.create("Semillas")
    center = NarrativeEntity(name="Centro")
    project_service.active_project.entities.append(center)
    project_service.active_project.touch()
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(project_provider=lambda: project_service.active_project)
    view.center_entity(center.id)
    return project_service, view, center


class TestSeedsInZones:
    def test_sync_places_seeds_by_zone(self, qapp):
        _, view, _ = _view_with_center()
        view.canvas.sync_seeds(
            [
                ("cand-1", "raices", "Guerra que arraiga"),
                ("cand-2", "brotes", "Leyenda derivada"),
                ("cand-3", "entorno", "Aliada propuesta"),
            ]
        )
        assert view.canvas.seeds_in_zone("raices") == ["cand-1"]
        assert view.canvas.seeds_in_zone("brotes") == ["cand-2"]
        assert view.canvas.seeds_in_zone("entorno") == ["cand-3"]
        assert set(view.canvas.seed_ids()) == {"cand-1", "cand-2", "cand-3"}

    def test_seed_item_is_visually_distinct_and_clickable(self, qapp):
        _, view, _ = _view_with_center()
        view.canvas.sync_seeds([("cand-1", "raices", "Semilla")])
        seed_item = view.canvas._seed_items["cand-1"]
        assert getattr(seed_item, "is_seed", False) is True  # ≠ satélite/fantasma
        clicked: list[str] = []
        view.seedReviewRequested.connect(clicked.append)
        view.canvas.seedClicked.emit("cand-1")
        assert clicked == ["cand-1"]

    def test_bloom_and_wither_remove_the_seed(self, qapp):
        _, view, _ = _view_with_center()
        view.canvas.sync_seeds([("cand-1", "raices", "A"), ("cand-2", "brotes", "B")])
        view.canvas.bloom_seed("cand-1")
        view.canvas.wither_seed("cand-2")
        assert view.canvas.seed_ids() == []

    def test_recentering_clears_previous_center_seeds(self, qapp):
        project_service, view, center = _view_with_center()
        other = NarrativeEntity(name="Otra")
        project_service.active_project.entities.append(other)
        project_service.active_project.touch()
        view.canvas.sync_seeds([("cand-1", "raices", "Del centro anterior")])

        view.center_entity(other.id)
        assert view.canvas.seed_ids() == []  # la sincronización llega del workspace


class TestTextCards:
    def test_cards_render_preview_and_route_review(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel

        panel = WateringPanel(watering_service=None)
        candidate = Candidate(
            title="Editar cuerpo de Centro",
            proposed_data={"edit_proposed_value": "Texto propuesto más rico."},
        )
        panel.set_text_cards([candidate])
        assert panel.card_ids() == [candidate.id]
        seen: list[str] = []
        panel.reviewRequested.connect(seen.append)
        # El botón «Revisar» de la tarjeta enruta al flujo humano existente.
        button = None
        for i in range(panel.cards_layout.count()):
            widget = panel.cards_layout.itemAt(i).widget()
            for child in widget.findChildren(type(panel.water_button)):
                if child.text() == "Revisar":
                    button = child
        assert button is not None
        button.click()
        assert seen == [candidate.id]

    def test_set_text_cards_replaces_previous(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel

        panel = WateringPanel(watering_service=None)
        panel.set_text_cards([Candidate(title="Una")])
        panel.set_text_cards([])
        assert panel.card_ids() == []


class TestWorkspaceWiring:
    """Pins del cableado (el CreationWorkspace no se construye headless)."""

    def test_sync_and_visibility_helpers_exist(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "def _sync_foco_seeds" in source
        assert "def _foco_visible_candidate_ids" in source
        assert "def _pending_foco_candidates" in source

    def test_chips_only_for_non_visible(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # Rehidratación: no añade chip si la semilla es visible en Foco.
        assert "cid not in self._foco_visible_candidate_ids()" in source
        # Staging: no añade chip si el hint apunta a la entidad enfocada.
        assert "if not visible_in_foco:" in source
        assert 'hint.get("center_entity_id")' in source

    def test_decision_keeps_focus_and_blooms_in_foco(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "foco_widget.canvas.bloom_seed(candidate_id)" in source
        assert "foco_widget.canvas.wither_seed(candidate_id)" in source
        # Aceptar mantiene el foco: recentra la MISMA entidad (sin push).
        keep_focus = "self.foco.center_entity(self.foco.current_entity_id())"
        assert keep_focus in source

    def test_review_routes_and_mode_switch_resync(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self.foco.seedReviewRequested.connect(self._open_candidate_review)" in source
        assert "panel.reviewRequested.connect(self._open_candidate_review)" in source
        assert "QTimer.singleShot(0, self._rehydrate_seed_notifications)" in source
