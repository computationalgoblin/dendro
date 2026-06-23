"""I19 (desktop) — tarjeta: Aceptar→canon (borrador), Revisar abre panel rico, badge enrich."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.app_context import AppContext  # noqa: E402
from hosts.DesktopHostPySide.views.import_export_view import ImportExportView  # noqa: E402
from hosts.DesktopHostPySide.widgets.import_candidate_review_panel import (  # noqa: E402
    ImportCandidateReviewPanel,
)
from packages.domain.entity import EntityType, NarrativeEntity  # noqa: E402
from packages.domain.import_models import ImportCandidate, ImportReviewState  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeIC:
    def __init__(self, candidate):
        self._candidate = candidate
        self.applied = None

    def list_baskets(self):
        basket = type("B", (), {"id": "b1", "source_id": "s1", "segments": [],
                                "import_candidates": [self._candidate], "import_mode": "canon"})()
        return Ok([basket])

    def get_basket(self, bid):
        return self.list_baskets().value[0] if bid == "b1" else None

    def apply_to_canon(self, basket_id, candidate_id):
        self.applied = (basket_id, candidate_id)
        return Ok(object())


class _FakeDrawer:
    def __init__(self):
        self.content = None
        self.opened = False

    def set_content(self, widget, title=""):
        self.content = widget

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False


class _Ctrl:
    def __init__(self, proj):
        self.ps = type("PS", (), {"active_project": proj, "_current_path": Path("/tmp/x.json")})()


def _candidate(**payload):
    base = {"kind": "entity", "name": "Eldrin", "entity_type": "personaje",
            "summary": "Mago anciano del Norte."}
    base.update(payload)
    return ImportCandidate(id="cand-1", segment_id="seg-1", candidate_type="entidad",
                           proposed_data=base, review_state=ImportReviewState.PENDIENTE)


def _view(qapp, proj, candidate):
    ctx = AppContext()
    view = ImportExportView(ctx, _Ctrl(proj))
    view.ic = _FakeIC(candidate)
    return view, ctx


def test_accept_button_applies_to_canon(qapp):
    view, _ = _view(qapp, Project(name="V"), _candidate())
    view._accept_ids("b1", "cand-1")
    assert view.ic.applied == ("b1", "cand-1")


def test_revisar_opens_rich_panel(qapp):
    proj = Project(name="V")
    cand = _candidate()
    view, ctx = _view(qapp, proj, cand)
    ctx.drawer = _FakeDrawer()
    view._open_review_panel("b1", "cand-1", cand)
    assert isinstance(ctx.drawer.content, ImportCandidateReviewPanel)
    assert ctx.drawer.opened is True


def test_enrich_target_name_resolves(qapp):
    proj = Project(name="V")
    proj.entities = [NarrativeEntity(id="ent-1", name="Eldrin", entity_type=EntityType.PERSONAJE)]
    view, _ = _view(qapp, proj, _candidate())
    name = view._enrich_target_name({"enrich_target_id": "ent-1"})
    assert name == "Eldrin"


# ── Bug 2: candidatos decididos desaparecen del menú de tarjetas ──────────────


class _FakeICMulti:
    def __init__(self, candidates):
        self._candidates = candidates

    def list_baskets(self):
        basket = type("B", (), {"id": "b1", "source_id": "s1", "segments": [],
                                "import_candidates": self._candidates, "import_mode": "canon"})()
        return Ok([basket])


def _view_multi(qapp, proj, candidates):
    view = ImportExportView(AppContext(), _Ctrl(proj))
    view.ic = _FakeICMulti(candidates)
    return view


def _pending_candidate_ids(view):
    return [c.id for _b, c in view._filtered_rows(view._rows()) if c is not None]


def test_accepted_candidate_hidden_from_cards(qapp):
    cand = _candidate()
    cand.review_state = ImportReviewState.ACEPTADO
    view = _view_multi(qapp, Project(name="V"), [cand])
    assert _pending_candidate_ids(view) == []


def test_decided_hidden_pending_shown(qapp):
    pend = _candidate()
    acc = ImportCandidate(id="c-acc", segment_id="s", candidate_type="entidad",
                          proposed_data={"kind": "entity", "name": "A", "summary": "x"},
                          review_state=ImportReviewState.ACEPTADO)
    rej = ImportCandidate(id="c-rej", segment_id="s", candidate_type="entidad",
                          proposed_data={"kind": "entity", "name": "B", "summary": "x"},
                          review_state=ImportReviewState.RECHAZADO)
    fus = ImportCandidate(id="c-fus", segment_id="s", candidate_type="entidad",
                          proposed_data={"kind": "entity", "name": "C", "summary": "x"},
                          review_state=ImportReviewState.FUSIONADO)
    view = _view_multi(qapp, Project(name="V"), [pend, acc, rej, fus])
    # Solo el pendiente sobrevive al filtro de tarjetas.
    assert _pending_candidate_ids(view) == ["cand-1"]


# ── Bug 1: el extracto lee body/extended_description, no solo summary ─────────


def test_excerpt_reads_body_when_no_summary(qapp):
    from hosts.DesktopHostPySide.views.import_export_view import _source_excerpt
    cand = ImportCandidate(id="c", segment_id="s", candidate_type="entidad",
                           proposed_data={"kind": "entity", "name": "X",
                                          "body": "Cuerpo extenso del candidato."},
                           review_state=ImportReviewState.PENDIENTE)
    assert "Cuerpo extenso" in _source_excerpt(cand)


def test_excerpt_reads_extended_description(qapp):
    from hosts.DesktopHostPySide.views.import_export_view import _source_excerpt
    cand = ImportCandidate(id="c", segment_id="s", candidate_type="entidad",
                           proposed_data={"kind": "entity", "name": "X",
                                          "extended_description": "Descripción larga."},
                           review_state=ImportReviewState.PENDIENTE)
    assert "Descripción larga" in _source_excerpt(cand)


# ── Bug 3: tarjetas en una columna (cabe el contenido) ────────────────────────


def test_cards_render_in_single_column(qapp):
    from hosts.DesktopHostPySide.views.import_export_view import _CARDS_COLUMNS
    assert _CARDS_COLUMNS == 1
    # Render real: refrescar con un candidato no debe lanzar y deja la tarjeta.
    view = _view_multi(qapp, Project(name="V"), [_candidate()])
    view.refresh()
    assert view.cards_grid.count() >= 1

