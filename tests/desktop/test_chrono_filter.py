"""BETA2-FOCO-33 — filtros de la Cronología (réplica del Mapa aplicable a la línea
de tiempo): embudo + popover con tipo/anillo/estado canon (+ ocultar secretas).

La cronología NO tiene aristas, así que los combos de relación/rama del popover del
Mapa se ocultan. El estado sigue viajando como ``VisualFilterState`` y se traduce a
``ChronoScope`` en el workspace; ``build_chrono_layout`` ya respeta esos campos.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView
    from hosts.DesktopHostPySide.widgets.filter_popover import FilterPopover


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ent(eid, name, *, kind="personaje", ring="r0", birth=20, death=None,
         visibility="visible_usuario", canon="canonico"):
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind, layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=death, custom_metadata={}, metadata={},
        visibility_state=visibility, canon_state=canon,
    )


def _layer(lid, name, rank):
    return SimpleNamespace(id=lid, name=name, metadata={"causal_rank": float(rank)},
                           order=rank, is_visible=True)


def _project():
    ents = [
        _ent("a", "A", ring="r0"),
        _ent("b", "B", ring="r0", kind="lugar"),
        _ent("c", "C", ring="r1"),
    ]
    return SimpleNamespace(
        entities=ents, relations=[],
        world_layers=[_layer("r0", "Uno", 0), _layer("r1", "Dos", 1)],
        causal_milestones=[],
        project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}),
    )


def _view():
    v = ChronoCanvasView()
    v._collapse_default = False
    v.set_atmosphere_context(SimpleNamespace(creation_chrono_expanded_ids=[]))
    v.resize(900, 500)
    v.set_project(_project())
    return v


class TestChronoFilterPopover:
    def test_chrono_variant_shows_only_applicable_filters(self, qapp):
        proj = _project()
        pop = FilterPopover(
            project_provider=lambda: proj,
            on_apply=lambda s: None,
            on_clear=lambda: None,
            mode="chrono",
        )
        # BETA2-FOCO-38: solo Tipo y Anillo en el formulario…
        assert pop.entity_type.parentWidget() is not None
        assert pop.layer.parentWidget() is not None
        # …ni Estado canon, ni Ocultar secretas, ni relación/rama (obsoletos).
        assert pop.canon.parentWidget() is None
        assert pop.hide_secret.parentWidget() is None
        assert pop.relation_type.parentWidget() is None
        assert pop.relation_family.parentWidget() is None
        assert pop.tree.parentWidget() is None
        assert pop.show_relations.parentWidget() is None

    def test_map_variant_keeps_relation_filters(self, qapp):
        proj = _project()
        pop = FilterPopover(
            project_provider=lambda: proj,
            on_apply=lambda s: None,
            on_clear=lambda: None,
        )
        assert pop.relation_type.parentWidget() is not None
        assert pop.tree.parentWidget() is not None
        assert pop.canon.parentWidget() is not None  # el Estado sigue en el Mapa

    def test_chrono_tipo_lists_offered_and_present(self, qapp):
        # BETA2-FOCO-38: el Tipo de la Cronología = ofrecidos ∪ presentes.
        proj = _project()  # presentes: personaje, lugar
        pop = FilterPopover(
            project_provider=lambda: proj,
            on_apply=lambda s: None,
            on_clear=lambda: None,
            mode="chrono",
        )
        values = {pop.entity_type.itemData(i) for i in range(pop.entity_type.count())}
        # Ofrecidos aunque no estén presentes en el proyecto:
        assert {"faccion", "personaje", "sistema_magico"} <= values
        # Presentes que no son "ofrecidos" también aparecen:
        assert "lugar" in values
        # El Mapa (no chrono) solo lista los tipos presentes.
        pop_map = FilterPopover(
            project_provider=lambda: proj, on_apply=lambda s: None, on_clear=lambda: None
        )
        map_values = {pop_map.entity_type.itemData(i) for i in range(pop_map.entity_type.count())}
        assert "faccion" not in map_values


class TestChronoFilterApply:
    def test_apply_scope_filter_narrows_and_counts(self, qapp):
        v = _view()
        v.apply_scope_filter(entity_types=["lugar"])
        assert v._current_scope().entity_types == frozenset({"lugar"})
        assert v.active_filter_count() == 1
        # El rebuild deja solo la entidad de tipo 'lugar' (b).
        ids = {ln.entity_id for ln in v._layout.lifelines}
        assert ids == {"b"}

    def test_apply_multiple_and_clear(self, qapp):
        # BETA2-FOCO-38: la Cronología filtra por Tipo + Anillo.
        v = _view()
        v.apply_scope_filter(entity_types=["personaje"], ring_ids=["r1"])
        assert v.active_filter_count() == 2
        assert v._current_scope().entity_types == frozenset({"personaje"})
        v.clear_scope_filter()
        assert v.active_filter_count() == 0
        assert v._current_scope().entity_types == frozenset()


class TestChronoFilterFunnel:
    def test_filter_anchor_and_emit(self, qapp):
        v = _view()
        assert v.filter_anchor() is v._filter_btn
        fired = []
        v.filterRequested.connect(lambda: fired.append(True))
        v._filter_btn.click()
        assert fired == [True]

    def test_badge_count_visibility(self, qapp):
        v = _view()
        v.set_filter_badge_count(2)
        assert not v._filter_badge.isHidden()
        assert v._filter_badge.text() == "2"
        v.set_filter_badge_count(0)
        assert v._filter_badge.isHidden()

    def test_workspace_wires_chrono_filter(self, qapp):
        src = Path(__file__).resolve().parents[2] / "hosts/DesktopHostPySide/views/workspaces.py"
        text = src.read_text(encoding="utf-8")
        assert "self.chrono.filterRequested.connect(self._open_chrono_filter_popover)" in text
        assert "popover.open_below(self.chrono.filter_anchor())" in text
        assert 'mode="chrono"' in text
