from __future__ import annotations

import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.views.import_export_view import ImportExportView
    from packages.domain.import_models import (
        DocumentSegment,
        ImportBasket,
        ImportCandidate,
        ImportReviewState,
    )
    from packages.domain.result import Ok


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


class FakeImportController:
    def __init__(self, basket):
        self.basket = basket

    def list_baskets(self):
        return Ok([self.basket])

    def get_basket(self, bid):
        assert bid == self.basket.id
        return Ok(self.basket)


class FakeController:
    ps = None


def test_import_export_rows_use_import_candidates_not_legacy_candidates(qapp):
    basket = ImportBasket(
        id="basket-full-id-123",
        source_id="source-full-id-456",
        segments=[
            DocumentSegment(id="segment-full-id-789", source_id="source-full-id-456")
        ],
        import_candidates=[
            ImportCandidate(
                id="candidate-full-id-999",
                segment_id="segment-full-id-789",
                candidate_type="entidad",
                proposed_data={"name": "Aria"},
                confidence=0.73,
                possible_duplicates=["entity-1"],
                possible_contradictions=["issue-1"],
                review_state=ImportReviewState.PENDIENTE,
            )
        ],
    )
    ctx = AppContext()
    view = ImportExportView(ctx, FakeController())
    view.ic = FakeImportController(basket)

    rows = view._rows()
    assert len(rows) == 1
    assert rows[0][0].id == basket.id
    assert rows[0][1].id == "candidate-full-id-999"

    # Render por tarjetas (ya no hay tabla técnica): refrescar no rompe y hay tarjeta.
    view.refresh()
    assert view.cards_grid.count() >= 1

    # Detalle limpio del candidato seleccionado: muestra el nombre, NO ids crudos.
    view.selected_basket_id = basket.id
    view.selected_candidate_id = "candidate-full-id-999"
    view._show_detail()
    clean_detail = view.detail.toPlainText()
    assert "Aria" in clean_detail
    assert "candidate-full-id-999" not in clean_detail
    assert "segment-full-id-789" not in clean_detail
