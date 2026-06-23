"""I18 (desktop) — ImportCandidateReviewPanel: ficha editable + aceptar→canon."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.import_candidate_review_panel import (  # noqa: E402
    ImportCandidateReviewPanel,
)
from packages.domain.import_models import ImportCandidate, ImportReviewState  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Ok  # noqa: E402
from packages.domain.world_layer import WorldLayer  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeController:
    def __init__(self):
        self.edited = None
        self.applied = None
        self.rejected = None

    def edit(self, basket_id, cand_id, data):
        self.edited = (basket_id, cand_id, dict(data))
        return Ok(None)

    def apply_to_canon(self, basket_id, cand_id):
        self.applied = (basket_id, cand_id)
        return Ok(object())

    def reject(self, basket_id, cand_id):
        self.rejected = (basket_id, cand_id)
        return Ok(None)


def _entity_candidate(**payload):
    base = {"kind": "entity", "name": "Eldrin", "entity_type": "personaje",
            "summary": "Mago anciano.", "body": "Custodio de la Torre."}
    base.update(payload)
    return ImportCandidate(
        id="cand-1", segment_id="seg-1", candidate_type="entidad",
        proposed_data=base, review_state=ImportReviewState.PENDIENTE,
    )


def _project_with_ring():
    proj = Project(name="I18")
    proj.world_layers = [WorldLayer(id="layer_narrativa", name="Narrativa", order=14)]
    return proj


def test_panel_shows_rich_fields(qapp):
    proj = _project_with_ring()
    panel = ImportCandidateReviewPanel(
        _entity_candidate(), _FakeController(), proj, basket_id="b1"
    )
    assert panel.name_edit.text() == "Eldrin"
    assert "Mago anciano" in panel.summary_edit.toPlainText()
    assert "Custodio" in panel.body_edit.toPlainText()
    # Combo de anillo poblado con la capa del proyecto.
    assert panel.ring_combo is not None
    assert panel.ring_combo.findData("layer_narrativa") >= 0


def test_accept_edits_then_applies_to_canon(qapp):
    proj = _project_with_ring()
    ctrl = _FakeController()
    decisions = []
    panel = ImportCandidateReviewPanel(
        _entity_candidate(), ctrl, proj, basket_id="b1",
        on_decision=lambda cid, d: decisions.append((cid, d)),
    )
    # Editar el cuerpo y elegir anillo.
    panel.body_edit.setPlainText("Cuerpo revisado por el usuario.")
    panel.ring_combo.setCurrentIndex(panel.ring_combo.findData("layer_narrativa"))
    panel._accept()

    assert ctrl.edited is not None
    _, _, data = ctrl.edited
    assert data["body"] == "Cuerpo revisado por el usuario."
    assert data["ring_id"] == "layer_narrativa"
    assert data["kind"] == "entity"
    # Tras editar, aplica a canon (un paso).
    assert ctrl.applied == ("b1", "cand-1")
    assert decisions == [("cand-1", "accept")]


def test_enrich_banner_shown(qapp):
    proj = _project_with_ring()
    proj_entities_id = "ent-eldrin"
    from packages.domain.entity import EntityType, NarrativeEntity
    proj.entities = [NarrativeEntity(id=proj_entities_id, name="Eldrin", entity_type=EntityType.PERSONAJE)]
    cand = _entity_candidate(presentation_kind="enrich_existing", enrich_target_id=proj_entities_id)
    panel = ImportCandidateReviewPanel(cand, _FakeController(), proj, basket_id="b1")
    # El aviso de enriquecimiento aparece con el nombre del objetivo.
    labels = panel.findChildren(type(panel.status))
    assert any("Enriquece" in lbl.text() for lbl in labels)


def test_reject_calls_controller(qapp):
    panel = ImportCandidateReviewPanel(
        _entity_candidate(), _FakeController(), _project_with_ring(), basket_id="b1"
    )
    panel._reject()
    assert panel.controller.rejected == ("b1", "cand-1")
