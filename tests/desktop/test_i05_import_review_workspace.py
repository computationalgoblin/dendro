from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.import_controller import ImportController
    from hosts.DesktopHostPySide.views.import_export_view import ImportExportView
    from packages.domain.import_models import ImportBasket, ImportCandidate, ImportReviewState
    from packages.domain.project import Project
    from packages.domain.result import Ok


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i05-project.json")


class FakeRootController:
    def __init__(self, project):
        self.ps = FakeProjectService(project)


class FakeImportController:
    def __init__(self, basket):
        self.basket = basket
        self.edits = []
        self.accepted = []
        self.rejected = []

    def list_baskets(self):
        return Ok([self.basket])

    def get_basket(self, bid):
        return Ok(self.basket)

    def edit(self, basket_id, candidate_id, data):
        self.edits.append((basket_id, candidate_id, data))
        for candidate in self.basket.import_candidates:
            if candidate.id == candidate_id:
                candidate.proposed_data.update(data)
                candidate.review_state = ImportReviewState.EDITADO
        return Ok(None)

    def apply_to_canon(self, basket_id, candidate_id):
        self.accepted.append((basket_id, candidate_id))
        return Ok(None)

    def accept(self, basket_id, candidate_id):
        return self.apply_to_canon(basket_id, candidate_id)

    def reject(self, basket_id, candidate_id):
        self.rejected.append((basket_id, candidate_id))
        for candidate in self.basket.import_candidates:
            if candidate.id == candidate_id:
                candidate.review_state = ImportReviewState.RECHAZADO
        return Ok(None)

    def analyze_duplicates(self, basket_id):
        return Ok([])


def _candidate(cid: str, kind: str, name: str, *, ctype: str = "entidad") -> ImportCandidate:
    return ImportCandidate(
        id=cid,
        segment_id=f"seg-{cid}",
        candidate_type=ctype,
        proposed_data={
            "kind": kind,
            "name": name,
            "summary": f"Resumen {name}",
            "source_references": [{
                "source_name": "lore.md",
                "section_path": "Capitulo",
                "quote_excerpt": f"Texto fuente de {name}",
            }],
        },
        confidence=0.8,
        review_state=ImportReviewState.PENDIENTE,
    )


def _view(project=None):
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    project = project or Project(name="I05")
    return ImportExportView(ctx, FakeRootController(project))


def test_i05_empty_batch_is_shown(qapp):
    basket = ImportBasket(id="basket-empty", source_id="source-1")
    view = _view()
    view.ic = FakeImportController(basket)

    view.refresh()

    assert "1 batch" in view.summary_label.text()
    assert "sin candidatos" in view.summary_label.text()
    assert view.cards_grid.count() >= 1


def test_i05_candidates_are_filterable_by_type(qapp):
    basket = ImportBasket(
        id="basket-1",
        source_id="source-1",
        import_candidates=[
            _candidate("entity-1", "entity", "Eldrin"),
            _candidate("branch-1", "branch", "Orden", ctype="entidad"),
            _candidate("relation-1", "relation", "Protege", ctype="relacion"),
            _candidate("milestone-1", "milestone", "Batalla", ctype="cambio"),
        ],
    )
    view = _view()
    view.ic = FakeImportController(basket)
    view.refresh()

    view.kind_filter.setCurrentIndex(view.kind_filter.findData("relation"))
    rows = view._filtered_rows(view._rows())

    assert len(rows) == 1
    assert rows[0][1].id == "relation-1"
    assert "Relaciones: 1" in view.summary_label.text()


def test_i05_candidate_can_be_opened_and_edited(qapp):
    candidate = _candidate("entity-1", "entity", "Eldrin")
    basket = ImportBasket(id="basket-1", source_id="source-1", import_candidates=[candidate])
    view = _view()
    view.ic = FakeImportController(basket)

    result = view._save_candidate_edit("basket-1", "entity-1", {"name": "Eldrin Revisado", "body": "Texto"})

    assert isinstance(result, Ok)
    assert candidate.proposed_data["name"] == "Eldrin Revisado"
    assert candidate.proposed_data["body"] == "Texto"
    assert candidate.review_state is ImportReviewState.EDITADO


def test_i05_entity_candidate_accept_creates_canon_via_application_service(qapp):
    project = Project(name="I05")
    candidate = _candidate("entity-1", "entity", "Eldrin")
    candidate.proposed_data["entity_type"] = "personaje"
    basket = ImportBasket(id="basket-1", source_id="source-1", import_candidates=[candidate])
    project.import_baskets.append(basket)
    view = _view(project)
    view.ic = ImportController(project_service=view.controller.ps)

    view._accept_ids("basket-1", "entity-1")

    assert len(project.entities) == 1
    assert project.entities[0].name == "Eldrin"
    assert project.entities[0].custom_metadata["import_candidate_id"] == "entity-1"
    assert candidate.review_state is ImportReviewState.ACEPTADO


def test_i05_relation_candidate_reject_does_not_modify_canon(qapp):
    project = Project(name="I05")
    candidate = _candidate("relation-1", "relation", "Protege", ctype="relacion")
    basket = ImportBasket(id="basket-1", source_id="source-1", import_candidates=[candidate])
    project.import_baskets.append(basket)
    view = _view(project)
    view.ic = ImportController(project_service=view.controller.ps)

    view._reject_ids("basket-1", "relation-1")

    assert len(project.relations) == 0
    assert candidate.review_state is ImportReviewState.RECHAZADO


def test_i05_merge_suggestion_is_visible(qapp):
    candidate = _candidate("merge-1", "merge_suggestion", "Fusionar Eldrin", ctype="fusion")
    basket = ImportBasket(id="basket-1", source_id="source-1", import_candidates=[candidate])
    view = _view()
    view.ic = FakeImportController(basket)

    view.refresh()
    view._select_card("basket-1", "merge-1")

    assert "Fusiones: 1" in view.summary_label.text()
    assert "Sugerencia de fusion" in view.detail.toPlainText()


def test_i05_normal_mode_hides_ids_and_raw_json(qapp):
    candidate = _candidate("candidate-full-id-999", "entity", "Aria")
    basket = ImportBasket(id="basket-full-id-123", source_id="source-full-id-456", import_candidates=[candidate])
    view = _view()
    view.ic = FakeImportController(basket)

    view.refresh()
    view._select_card("basket-full-id-123", "candidate-full-id-999")
    detail = view.detail.toPlainText()

    assert "candidate-full-id-999" not in detail
    assert "source-full-id-456" not in detail
    assert "Payload" not in detail
    assert "{" not in detail

