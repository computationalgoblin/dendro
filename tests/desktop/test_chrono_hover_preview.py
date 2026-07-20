"""BETA2-HOVER-03: previsualización flotante al hover en la cronología."""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.chrono_canvas import (
    build_chrono_layout,  # noqa: F401 (harness)
)
from packages.domain.causal_milestone import CausalMilestone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


def _ent(eid, name, *, kind="personaje", ring="ring1", birth=0, brief="", image=""):
    meta = {}
    if image:
        meta["_image_path"] = image
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind, layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=None, custom_metadata=meta,
        brief_description=brief,
    )


def _project(entities, milestones=(), layers=("ring1",)):
    chronology = SimpleNamespace(
        present_year=400,
        eras=[SimpleNamespace(id="e0", name="Era", start_year=-100, end_year=None, order=0)],
        metadata={},
    )
    world_layers = [
        SimpleNamespace(id=lid, name=f"Anillo {lid}", is_visible=True, order=i + 1,
                        metadata={}, description=f"Descripción de {lid}", color="#8B7A36")
        for i, lid in enumerate(layers)
    ]
    return SimpleNamespace(
        entities=list(entities), relations=[], world_layers=world_layers,
        causal_milestones=list(milestones), project_chronology=chronology,
        entity_by_id=lambda eid, es=entities: next(
            (e for e in es if str(e.id) == str(eid)), None
        ),
    )


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _view(qapp, project):
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
    view = ChronoCanvasView()
    view.resize(1000, 700)
    view.set_project(project)
    view.show()
    view.fit_all()
    return view


class TestChronoHoverPreview:
    def test_set_assets_root(self, qapp):
        view = _view(qapp, _project([_ent("e1", "A", brief="hola")]))
        view.set_assets_root("C:/proyecto.assets")
        assert view.scene()._portrait_assets_root is not None

    def test_entity_content_full_brief(self, qapp):
        long_brief = "palabra " * 60
        view = _view(qapp, _project([_ent("e1", "Sharif", brief=long_brief, image="p.png")]))
        content = view._entity_hover_content("e1")
        assert content is not None
        assert content.title == "Sharif"
        assert content.brief == long_brief  # entero
        assert content.kind == "entidad"
        assert content.image_path == "p.png"

    def test_branch_content_is_kind_rama(self, qapp):
        view = _view(qapp, _project([_ent("t", "Casa", kind="contenedor", brief="una casa")]))
        content = view._entity_hover_content("t")
        assert content is not None
        assert content.kind == "rama"

    def test_hito_content(self, qapp):
        hito = CausalMilestone(
            id="h1", title="La Guerra", description="un conflicto largo", year=100
        )
        view = _view(qapp, _project([], [hito]))
        content = view._hito_hover_content("h1")
        assert content is not None
        assert content.title == "La Guerra"
        assert content.brief == "un conflicto largo"
        assert content.kind == "hito"

    def test_ring_content(self, qapp):
        view = _view(qapp, _project([_ent("e1", "A", brief="x")]))
        content = view._ring_hover_content("ring1")
        assert content is not None
        assert content.kind == "anillo"
        assert "ring1" in content.brief  # "Descripción de ring1"

    def test_era_content(self, qapp):
        proj = _project([_ent("e1", "A", brief="x")])
        proj.project_chronology.eras = [
            SimpleNamespace(id="e0", name="Edad Media", start_year=100, end_year=300,
                            order=0, description="siglos de hierro")
        ]
        view = _view(qapp, proj)
        content = view._era_hover_content("e0")
        assert content is not None
        assert content.kind == "era"
        assert content.title == "Edad Media"
        assert content.brief == "siglos de hierro"
        assert "100" in content.meta and "300" in content.meta

    def test_resolver_dispatches_era_by_role(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import _ERA_ID_ROLE

        proj = _project([_ent("e1", "A", brief="x")])
        proj.project_chronology.eras = [
            SimpleNamespace(id="e0", name="Edad", start_year=1, end_year=9, order=0,
                            description="desc")
        ]
        view = _view(qapp, proj)
        fake = SimpleNamespace(
            data=lambda role: "e0" if role == _ERA_ID_ROLE else None,
            parentItem=lambda: None,
        )
        view.itemAt = lambda _p, it=fake: it
        from PySide6.QtCore import QPoint

        content = view._hover_content_at(QPoint(5, 5))
        assert content is not None and content.kind == "era" and content.title == "Edad"

    def test_resolver_dispatches_by_item(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import _MILESTONE_ID_ROLE

        hito = CausalMilestone(id="h1", title="Hito", description="d", year=100)
        view = _view(qapp, _project([_ent("e1", "A", brief="x")], [hito]))
        # simular un item con rol de hito bajo el cursor
        fake = SimpleNamespace(
            data=lambda role: "h1" if role == _MILESTONE_ID_ROLE else None,
            parentItem=lambda: None,
        )
        view.itemAt = lambda _p, it=fake: it
        from PySide6.QtCore import QPoint

        content = view._hover_content_at(QPoint(5, 5))
        assert content is not None and content.title == "Hito"
