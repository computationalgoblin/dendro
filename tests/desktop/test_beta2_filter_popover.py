"""BETA2-UI2-10: FilterPopover — filtros visuales compactos del pill temporal.

Sustituye al CreationFilterPanel del drawer: se puebla desde un provider del
proyecto (solo lectura), restaura el estado activo, notifica cambios por
``on_apply(VisualFilterState)`` y limpia con ``on_clear`` sin disparar applies
intermedios. Sin secciones de CRUD de anillos/eras (relegado a lo contextual).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


def _project():
    return SimpleNamespace(
        entities=[
            SimpleNamespace(
                id="e1", name="Aria", entity_type="personaje", canon_state="canon"
            ),
            SimpleNamespace(
                id="t1", name="Casa Real", entity_type="contenedor", canon_state="canon"
            ),
            SimpleNamespace(
                id="e2", name="Bosque", entity_type="lugar", canon_state="borrador"
            ),
        ],
        relations=[SimpleNamespace(id="r1", relation_type="conoce")],
        world_layers=[
            SimpleNamespace(id="l1", name="Mundo físico", is_visible=True),
            SimpleNamespace(id="l2", name="Oculto", is_visible=False),
        ],
    )


def _popover(qapp, *, initial_state=None, applied=None, cleared=None):
    from hosts.DesktopHostPySide.widgets.filter_popover import FilterPopover

    return FilterPopover(
        project_provider=_project,
        initial_state=initial_state,
        on_apply=(applied.append if applied is not None else (lambda _s: None)),
        on_clear=((lambda: cleared.append(True)) if cleared is not None else (lambda: None)),
    )


def _data_values(combo):
    return [combo.itemData(i) for i in range(combo.count())]


def test_populates_from_project_provider(qapp):
    pop = _popover(qapp)
    assert "personaje" in _data_values(pop.entity_type)
    assert "lugar" in _data_values(pop.entity_type)
    assert "conoce" in _data_values(pop.relation_type)
    assert "canon" in _data_values(pop.canon)
    assert "borrador" in _data_values(pop.canon)
    assert "t1" in _data_values(pop.tree)  # solo contenedores son ramas
    # Solo capas visibles entran al combo de anillo
    assert "l1" in _data_values(pop.layer)
    assert "l2" not in _data_values(pop.layer)
    pop.deleteLater()


def test_restores_initial_state(qapp):
    from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState

    state = VisualFilterState(
        entity_types=("personaje",),
        layer_ids=("l1",),
        canon_states=("borrador",),
        show_relations=False,
    )
    pop = _popover(qapp, initial_state=state)
    assert pop.entity_type.currentData() == "personaje"
    assert pop.layer.currentData() == "l1"
    assert pop.canon.currentData() == "borrador"
    assert pop.show_relations.isChecked() is False
    # Lo no filtrado queda en "- Cualquiera -"
    assert pop.relation_type.currentData() == ""
    pop.deleteLater()


def test_change_applies_correct_state(qapp):
    applied = []
    pop = _popover(qapp, applied=applied)
    index = pop.entity_type.findData("lugar")
    pop.entity_type.setCurrentIndex(index)
    assert len(applied) == 1
    state = applied[-1]
    assert state.entity_types == ("lugar",)
    assert state.show_relations is True
    assert state.tree_id == ""

    pop.show_relations.setChecked(False)
    assert applied[-1].show_relations is False
    pop.deleteLater()


def test_clear_resets_and_calls_on_clear_only(qapp):
    from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState

    applied = []
    cleared = []
    pop = _popover(
        qapp,
        initial_state=VisualFilterState(entity_types=("personaje",), show_relations=False),
        applied=applied,
        cleared=cleared,
    )
    pop._clear()
    # Limpiar no encadena applies por cada combo reseteado (señales bloqueadas)
    assert applied == []
    assert cleared == [True]
    assert pop.entity_type.currentData() == ""
    assert pop.show_relations.isChecked() is True
    pop.deleteLater()


def test_no_ring_or_era_crud_inside_popover(qapp):
    from pathlib import Path

    source = Path("hosts/DesktopHostPySide/widgets/filter_popover.py").read_text(
        encoding="utf-8"
    )
    # El CRUD quedó relegado a los menús contextuales — el popover ni lo menta.
    assert "_build_rings_section" not in source
    assert "_build_eras_section" not in source
    assert "set_present_year" not in source
